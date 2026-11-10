"""
Vistas de Autenticación JWT, Perfiles de los 4 Actores (Sección 4.1 de la Guía)
y Panel de Moderación (EC-03).
Cumple estrictamente con:
- `django-architecture-enforcer`: Vistas delgadas que solo validan HTTP y delegan a `services.py` y `selectors.py`.
- `django-security-auditor`: Rate Limiting (`ScopedRateThrottle`) en Login y Registro + protección Anti-IDOR.
"""

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import generics, status, views, viewsets
from rest_framework.exceptions import PermissionDenied
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from accounts.models import EstablishmentCorrectionRequest, UserProfile
from accounts.permissions import (
    IsAuthenticatedAndNotSuspended,
    IsMerchantActor,
    IsModeratorActor,
)
from accounts.selectors import (
    get_all_profiles_for_moderation,
    get_correction_requests_for_actor,
    get_flagged_price_reports_for_moderation,
    get_or_create_actor_profile,
)
from accounts.serializers import (
    ActorProfileImageUploadSerializer,
    ActorProfileSerializer,
    ActorRegistrationSerializer,
    EstablishmentCorrectionRequestSerializer,
    ModeratorAccountManagementSerializer,
    ModeratorFlaggedPriceReportSerializer,
    ModeratorReviewReportSerializer,
    PricecolTokenObtainPairSerializer,
    TokenPairResponseSerializer,
)
from accounts.services import (
    AccountSecurityDomainError,
    approve_merchant_correction_by_moderator,
    create_merchant_correction_request,
    register_actor_account,
    review_flagged_price_report_by_moderator,
    set_profile_verification_status_by_moderator,
    update_actor_profile_image,
)
from catalog.services import InvalidImageError
from pricing.models import PriceReport


class ActorRegistrationAPIView(views.APIView):
    """
    Registro de cuentas para Consumidor (`CONSUMER`), Reportante (`REPORTER`) o Comercio (`MERCHANT`).
    Incluye Throttling (`auth_burst`) contra ataques de creación masiva de bots (Sybil Attack).
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_burst"
    serializer_class = ActorRegistrationSerializer

    @extend_schema(
        summary="Registrar cuenta de Actor (Retorna únicamente tokens JWT access y refresh)",
        request=ActorRegistrationSerializer,
        responses={201: TokenPairResponseSerializer},
        tags=["auth-and-profiles"],
    )
    def post(self, request: Request) -> Response:
        serializer = ActorRegistrationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v_data = serializer.validated_data

        try:
            profile = register_actor_account(
                username=v_data["username"],
                email=v_data["email"],
                password=v_data["password"],
                role=v_data["role"],
                accepted_data_policy=v_data["accepted_data_policy"],
                managed_establishment=v_data.get("managed_establishment"),
            )
        except AccountSecurityDomainError as exc:
            raise PermissionDenied(str(exc)) from exc

        refresh = RefreshToken.for_user(profile.user)
        return Response(
            {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
            },
            status=status.HTTP_201_CREATED,
        )


class PricecolLoginAPIView(TokenObtainPairView):
    """Inicio de sesión con Throttling contra fuerza bruta (`auth_burst`)."""

    serializer_class = PricecolTokenObtainPairSerializer
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_burst"

    @extend_schema(
        summary="Iniciar sesión (JWT) para Reportante, Comercio, Consumidor o Moderador",
        tags=["auth-and-profiles"],
    )
    def post(self, request: Request, *args, **kwargs) -> Response:
        return super().post(request, *args, **kwargs)


class PricecolTokenRefreshAPIView(TokenRefreshView):
    """Refrescar el token de acceso JWT."""

    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "auth_burst"

    @extend_schema(summary="Refrescar token JWT de acceso", tags=["auth-and-profiles"])
    def post(self, request: Request, *args, **kwargs) -> Response:
        return super().post(request, *args, **kwargs)


class CurrentActorProfileAPIView(generics.RetrieveUpdateAPIView):
    """
    Consulta el perfil propio (`/api/v1/auth/me/`) y permite subir/actualizar la foto de perfil (`profile_image`).
    Blindado contra Mass Assignment (`ActorProfileSerializer` tiene campos sensibles como `read_only`).
    """

    serializer_class = ActorProfileSerializer
    permission_classes = [IsAuthenticatedAndNotSuspended]
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_object(self) -> UserProfile:
        return get_or_create_actor_profile(user=self.request.user)

    @extend_schema(
        summary="Consultar perfil propio e impacto de aportes (Reportante / Comercio / Moderador)",
        tags=["auth-and-profiles"],
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)

    @extend_schema(
        summary="Actualizar perfil propio (soporta subida de `profile_image` en multipart/form-data con purga EXIF)",
        request=ActorProfileImageUploadSerializer,
        responses={200: ActorProfileSerializer},
        tags=["auth-and-profiles"],
    )
    def patch(self, request: Request, *args, **kwargs) -> Response:
        if "profile_image" in request.data or "profile_image" in request.FILES:
            profile = self.get_object()
            img_serializer = ActorProfileImageUploadSerializer(data=request.data)
            img_serializer.is_valid(raise_exception=True)
            uploaded_file = img_serializer.validated_data["profile_image"]
            try:
                updated_profile = update_actor_profile_image(
                    profile=profile,
                    uploaded_file=uploaded_file,
                    filename=getattr(uploaded_file, "name", ""),
                )
            except InvalidImageError as exc:
                return Response(
                    {"detail": str(exc)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                ActorProfileSerializer(updated_profile, context={"request": request}).data,
                status=status.HTTP_200_OK,
            )
        return super().patch(request, *args, **kwargs)


class CurrentActorAvatarUploadAPIView(views.APIView):
    """Endpoint explícito `POST /api/v1/auth/me/avatar/` para subir o actualizar la foto de perfil."""

    permission_classes = [IsAuthenticatedAndNotSuspended]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(
        summary="Subir o actualizar la foto de perfil del usuario autenticado (JPEG/PNG/WEBP <= 5MB, purga EXIF)",
        request=ActorProfileImageUploadSerializer,
        responses={200: ActorProfileSerializer},
        tags=["auth-and-profiles"],
    )
    def post(self, request: Request) -> Response:
        profile = get_or_create_actor_profile(user=request.user)
        serializer = ActorProfileImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded_file = serializer.validated_data["profile_image"]

        try:
            updated_profile = update_actor_profile_image(
                profile=profile,
                uploaded_file=uploaded_file,
                filename=getattr(uploaded_file, "name", ""),
            )
        except InvalidImageError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            ActorProfileSerializer(updated_profile, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


class MerchantCorrectionRequestViewSet(viewsets.ModelViewSet):
    """
    Actor Comercio (Tabla 4.1 y Consideración Ética 3 — Equidad entre comercios):
    Delega en `create_merchant_correction_request` que bloquea cualquier intento de IDOR
    sobre establecimientos de la competencia.
    """

    serializer_class = EstablishmentCorrectionRequestSerializer
    permission_classes = [IsMerchantActor]
    queryset = EstablishmentCorrectionRequest.objects.select_related("establishment").all()
    http_method_names = ["get", "post", "head", "options"]

    def get_queryset(self):
        return get_correction_requests_for_actor(user=self.request.user)

    @extend_schema(
        summary="Comercio: Solicitar corrección de información errónea de su propio negocio (Anti-IDOR)",
        tags=["merchant-actor"],
    )
    def create(self, request: Request, *args, **kwargs) -> Response:
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        v_data = serializer.validated_data

        try:
            correction = create_merchant_correction_request(
                merchant_user=request.user,
                establishment=v_data["establishment"],
                proposed_name=v_data.get("proposed_name", ""),
                proposed_neighborhood=v_data.get("proposed_neighborhood", ""),
                proposed_address=v_data.get("proposed_address", ""),
                justification=v_data["justification"],
            )
        except AccountSecurityDomainError as exc:
            raise PermissionDenied(str(exc)) from exc

        out = self.get_serializer(correction)
        return Response(out.data, status=status.HTTP_201_CREATED)


class ModeratorFlaggedReportsListAPIView(generics.ListAPIView):
    """Actor Moderador (Tabla 4.1): Lista reportes dudosos usando selector optimizado."""

    serializer_class = ModeratorFlaggedPriceReportSerializer
    permission_classes = [IsModeratorActor]

    def get_queryset(self):
        return get_flagged_price_reports_for_moderation()

    @extend_schema(
        summary="Moderador: Listar cola de reportes de precios dudosos o anómalos (EC-03)",
        tags=["moderator-actor"],
    )
    def get(self, request: Request, *args, **kwargs) -> Response:
        return super().get(request, *args, **kwargs)


class ModeratorReviewReportAPIView(views.APIView):
    """Actor Moderador: Aprueba o confirma como falso un reporte dudoso delegando a `accounts.services`."""

    permission_classes = [IsModeratorActor]

    @extend_schema(
        summary="Moderador: Aprobar o rechazar un reporte dudoso y preservar la integridad (EC-03)",
        request=ModeratorReviewReportSerializer,
        responses={200: ModeratorFlaggedPriceReportSerializer},
        tags=["moderator-actor"],
    )
    def post(self, request: Request, report_id: int) -> Response:
        report = get_object_or_404(
            PriceReport.objects.select_related("presentation", "establishment"),
            pk=report_id,
        )
        serializer = ModeratorReviewReportSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        updated_report = review_flagged_price_report_by_moderator(
            moderator_user=request.user,
            report=report,
            new_status=serializer.validated_data["new_status"],
            moderator_note=serializer.validated_data.get("moderator_note", ""),
        )
        return Response(ModeratorFlaggedPriceReportSerializer(updated_report).data, status=status.HTTP_200_OK)


class ModeratorAccountManagementViewSet(viewsets.ModelViewSet):
    """Actor Moderador: Gestión de cuentas de usuarios y suspensión de cuentas malintencionadas."""

    serializer_class = ModeratorAccountManagementSerializer
    permission_classes = [IsModeratorActor]
    queryset = get_all_profiles_for_moderation()
    http_method_names = ["get", "patch", "head", "options"]

    @extend_schema(
        summary="Moderador: Gestionar cuentas de usuarios y suspender actores malintencionados (Tabla 4.1)",
        tags=["moderator-actor"],
    )
    def partial_update(self, request: Request, *args, **kwargs) -> Response:
        target_profile: UserProfile = self.get_object()
        if target_profile.user.is_superuser and not request.user.is_superuser:
            raise PermissionDenied("Un moderador no puede alterar o suspender a un superusuario.")
        return super().partial_update(request, *args, **kwargs)

    def perform_update(self, serializer: ModeratorAccountManagementSerializer) -> None:
        previous_status = serializer.instance.verification_status
        profile = serializer.save()
        if profile.verification_status != previous_status:
            set_profile_verification_status_by_moderator(
                moderator_user=self.request.user,
                profile=profile,
                new_status=profile.verification_status,
            )


class ModeratorApproveCorrectionAPIView(views.APIView):
    """Actor Moderador: Aprueba y aplica una solicitud de corrección enviada por un Comercio."""

    permission_classes = [IsModeratorActor]
    serializer_class = EstablishmentCorrectionRequestSerializer

    @extend_schema(
        summary="Moderador: Aprobar y aplicar corrección de datos de un Comercio",
        request=None,
        responses={200: EstablishmentCorrectionRequestSerializer},
        tags=["moderator-actor"],
    )
    def post(self, request: Request, correction_id: int) -> Response:
        correction = get_object_or_404(
            EstablishmentCorrectionRequest.objects.select_related("establishment"),
            pk=correction_id,
        )
        approved = approve_merchant_correction_by_moderator(
            moderator_user=request.user,
            correction=correction,
            moderator_notes=str(request.data.get("moderator_notes", "")),
        )
        return Response(EstablishmentCorrectionRequestSerializer(approved).data, status=status.HTTP_200_OK)
