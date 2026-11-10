"""
Vistas de consulta y autocompletado rápido del Catálogo (EC-01, EC-04).
"""

from django.db.models import Q
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.response import Response

from accounts.permissions import (
    CanReportPricesPermission,
    IsAuthenticatedAndNotSuspended,
    IsMerchantActor,
    IsModeratorActor,
)
from accounts.selectors import get_or_create_actor_profile
from catalog.models import Establishment, Product, ProductPresentation
from catalog.serializers import (
    EstablishmentLogoImageUploadSerializer,
    EstablishmentSerializer,
    PresentationReferenceImageUploadSerializer,
    ProductMutationSerializer,
    ProductPresentationMutationSerializer,
    ProductPresentationSerializer,
    ProductRepresentativeImageUploadSerializer,
    ProductSerializer,
)
from catalog.services import (
    EstablishmentImagePermissionError,
    InvalidImageError,
    create_establishment_for_actor,
    deactivate_establishment_for_actor,
    update_establishment_for_actor,
    update_establishment_logo_image,
    update_presentation_reference_image,
    update_product_representative_image,
)


class EstablishmentViewSet(viewsets.ModelViewSet):
    """
    Directorio de establecimientos con ubicación en Armenia y Quindío y CRUD para Comercios (`MERCHANT`) / Moderadores.
    - Lectura (`GET`): Pública (soporta `?mine=true`, `?owner=<user_id>`, `?q=`, `?municipality=`, `?type=`).
    - Creación (`POST`): Exclusiva para `MERCHANT` o `MODERATOR` (asigna `owner = request.user` en relación 1 a muchos).
    - Edición y Eliminación (`PUT`, `PATCH`, `DELETE`): Protegido con Anti-IDOR estricto (solo el propietario `owner` o `MODERATOR`).
    """

    serializer_class = EstablishmentSerializer
    queryset = Establishment.objects.filter(is_active=True).select_related("owner")
    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def get_permissions(self):
        if self.action == "create":
            return [IsMerchantActor()]
        if self.action in ("update", "partial_update", "destroy", "upload_image"):
            return [IsAuthenticatedAndNotSuspended()]
        return []

    @extend_schema(
        summary="Listar o buscar establecimientos comerciales (soporta `?mine=true` para 'Mis establecimientos')",
        parameters=[
            OpenApiParameter("q", str, description="Búsqueda por nombre o barrio (autocompletado EC-01)."),
            OpenApiParameter("municipality", str, description="Filtrar por municipio (ej. Armenia, Calarcá)."),
            OpenApiParameter("type", str, description="Filtrar por tipo: NEIGHBORHOOD_SHOP, MINIMARKET, SUPERMARKET."),
            OpenApiParameter("mine", bool, description="Si es `true`, filtra los establecimientos que pertenecen al usuario autenticado."),
            OpenApiParameter("owner", int, description="Filtrar establecimientos por ID del usuario propietario (`owner`)."),
        ],
    )
    def list(self, request: Request, *args, **kwargs) -> Response:
        return super().list(request, *args, **kwargs)

    def get_queryset(self):
        qs = super().get_queryset()
        query = self.request.query_params.get("q", "").strip()
        municipality = self.request.query_params.get("municipality", "").strip()
        est_type = self.request.query_params.get("type", "").strip()
        mine = self.request.query_params.get("mine", "").strip().lower()
        owner_id = self.request.query_params.get("owner", "").strip()

        if mine in ("true", "1", "yes"):
            if not (self.request.user and self.request.user.is_authenticated):
                return qs.none()
            profile = get_or_create_actor_profile(user=self.request.user)
            owner_filter = Q(owner_id=self.request.user.id)
            if profile.managed_establishment_id is not None:
                owner_filter |= Q(id=profile.managed_establishment_id)
            qs = qs.filter(owner_filter)

        if owner_id.isdigit():
            qs = qs.filter(owner_id=int(owner_id))

        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(neighborhood__icontains=query)
                | Q(address__icontains=query)
            )
        if municipality:
            qs = qs.filter(municipality__iexact=municipality)
        if est_type:
            qs = qs.filter(establishment_type=est_type)

        return qs

    def create(self, request: Request, *args, **kwargs) -> Response:
        del args, kwargs
        profile = get_or_create_actor_profile(user=request.user)
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            establishment = create_establishment_for_actor(
                profile=profile,
                validated_data=serializer.validated_data,
            )
            if "logo_image" in request.FILES:
                uploaded_file = request.FILES["logo_image"]
                establishment = update_establishment_logo_image(
                    profile=profile,
                    establishment=establishment,
                    uploaded_file=uploaded_file,
                    filename=getattr(uploaded_file, "name", ""),
                )
        except EstablishmentImagePermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except InvalidImageError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            EstablishmentSerializer(establishment, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    def _handle_update(self, request: Request, *, partial: bool) -> Response:
        establishment = self.get_object()
        profile = get_or_create_actor_profile(user=request.user)
        serializer = self.get_serializer(establishment, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        try:
            updated = update_establishment_for_actor(
                profile=profile,
                establishment=establishment,
                validated_data=serializer.validated_data,
            )
            if "logo_image" in request.FILES:
                uploaded_file = request.FILES["logo_image"]
                updated = update_establishment_logo_image(
                    profile=profile,
                    establishment=updated,
                    uploaded_file=uploaded_file,
                    filename=getattr(uploaded_file, "name", ""),
                )
        except EstablishmentImagePermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        except InvalidImageError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            EstablishmentSerializer(updated, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    def update(self, request: Request, *args, **kwargs) -> Response:
        del args, kwargs
        return self._handle_update(request, partial=False)

    def partial_update(self, request: Request, *args, **kwargs) -> Response:
        del args, kwargs
        return self._handle_update(request, partial=True)

    def destroy(self, request: Request, *args, **kwargs) -> Response:
        del args, kwargs
        establishment = self.get_object()
        profile = get_or_create_actor_profile(user=request.user)
        try:
            deactivate_establishment_for_actor(
                profile=profile,
                establishment=establishment,
            )
        except EstablishmentImagePermissionError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_403_FORBIDDEN)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @extend_schema(
        summary="Subir o actualizar el logo/imagen de un establecimiento (Solo Comercio propietario o Moderador - Anti-IDOR)",
        request=EstablishmentLogoImageUploadSerializer,
        responses={200: EstablishmentSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="image",
        permission_classes=[IsAuthenticatedAndNotSuspended],
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def upload_image(self, request: Request, pk: int | None = None) -> Response:
        del pk
        establishment = self.get_object()
        profile = get_or_create_actor_profile(user=request.user)
        serializer = EstablishmentLogoImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded_file = serializer.validated_data["logo_image"]

        try:
            updated = update_establishment_logo_image(
                profile=profile,
                establishment=establishment,
                uploaded_file=uploaded_file,
                filename=getattr(uploaded_file, "name", ""),
            )
        except EstablishmentImagePermissionError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_403_FORBIDDEN,
            )
        except InvalidImageError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            EstablishmentSerializer(updated, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


class ProductViewSet(viewsets.ModelViewSet):
    """
    Catálogo de productos base y sus presentaciones.
    - Lectura pública (GET): abierta a cualquier consumidor sin autenticación.
    - Mutación (POST, PUT, PATCH, DELETE): reservada estrictamente al rol MODERATOR.
    Incluye el endpoint central `/api/v1/products/{id}/compare/` (EC-02, EC-04, EC-06).
    """

    queryset = Product.objects.filter(is_active=True).prefetch_related("presentations")

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ProductMutationSerializer
        return ProductSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy", "upload_image"):
            return [IsModeratorActor()]
        return []

    def partial_update(self, request: Request, *args, **kwargs) -> Response:
        response = super().partial_update(request, *args, **kwargs)
        if "product_image" in request.data or "product_image" in request.FILES:
            product = self.get_object()
            img_serializer = ProductRepresentativeImageUploadSerializer(data=request.data)
            img_serializer.is_valid(raise_exception=True)
            uploaded_file = img_serializer.validated_data["product_image"]
            try:
                updated_product = update_product_representative_image(
                    product=product,
                    uploaded_file=uploaded_file,
                    filename=getattr(uploaded_file, "name", ""),
                )
            except InvalidImageError as exc:
                return Response(
                    {"detail": str(exc)},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            return Response(
                ProductSerializer(updated_product, context={"request": request}).data,
                status=status.HTTP_200_OK,
            )
        return response

    @extend_schema(
        summary="Subir o actualizar la imagen representativa de un producto molde (Exclusivo Moderador, JPEG/PNG/WEBP <= 5MB, purga EXIF)",
        request=ProductRepresentativeImageUploadSerializer,
        responses={200: ProductSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="image",
        permission_classes=[IsModeratorActor],
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def upload_image(self, request: Request, pk: int | None = None) -> Response:
        del pk
        product = self.get_object()
        serializer = ProductRepresentativeImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded_file = serializer.validated_data["product_image"]

        try:
            updated = update_product_representative_image(
                product=product,
                uploaded_file=uploaded_file,
                filename=getattr(uploaded_file, "name", ""),
            )
        except InvalidImageError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            ProductSerializer(updated, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )

    def perform_destroy(self, instance: Product) -> None:
        """Borrado lógico para preservar la integridad referencial de reportes históricos."""
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    def get_queryset(self):
        qs = super().get_queryset()
        query = self.request.query_params.get("q", "").strip()
        category = self.request.query_params.get("category", "").strip()

        if query:
            qs = qs.filter(
                Q(name__icontains=query)
                | Q(aliases__icontains=query)
                | Q(presentations__brand__icontains=query)
                | Q(presentations__ean_barcode__iexact=query)
            ).distinct()
        if category:
            qs = qs.filter(category=category)

        return qs


class ProductPresentationViewSet(viewsets.ModelViewSet):
    """
    Consulta directa de presentaciones por código de barras EAN o producto (EC-01).
    - Lectura pública (GET): abierta a cualquier consumidor.
    - Mutación (POST, PUT, PATCH, DELETE): reservada exclusivamente al rol MODERATOR.
    - Subida de imagen (POST /api/v1/presentations/{id}/image/): permitida para usuarios que aportan precios o moderador.
    """

    queryset = ProductPresentation.objects.filter(is_active=True).select_related("product")

    def get_serializer_class(self):
        if self.action in ("create", "update", "partial_update"):
            return ProductPresentationMutationSerializer
        return ProductPresentationSerializer

    def get_permissions(self):
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsModeratorActor()]
        if self.action == "upload_image":
            return [CanReportPricesPermission()]
        return []

    def perform_destroy(self, instance: ProductPresentation) -> None:
        """Borrado lógico de la presentación."""
        instance.is_active = False
        instance.save(update_fields=["is_active"])

    def get_queryset(self):
        qs = super().get_queryset()
        ean = self.request.query_params.get("ean", "").strip()
        product_id = self.request.query_params.get("product_id", "").strip()

        if ean:
            qs = qs.filter(ean_barcode=ean)
        if product_id.isdigit():
            qs = qs.filter(product_id=int(product_id))
        return qs

    @extend_schema(
        summary="Subir o actualizar la imagen de referencia de una presentación (JPEG/PNG/WEBP <= 5MB, purga EXIF)",
        request=PresentationReferenceImageUploadSerializer,
        responses={200: ProductPresentationSerializer},
    )
    @action(
        detail=True,
        methods=["post"],
        url_path="image",
        permission_classes=[CanReportPricesPermission],
        parser_classes=[MultiPartParser, FormParser, JSONParser],
    )
    def upload_image(self, request: Request, pk: int | None = None) -> Response:
        del pk
        presentation = self.get_object()
        serializer = PresentationReferenceImageUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        uploaded_file = serializer.validated_data["reference_image"]

        try:
            updated = update_presentation_reference_image(
                presentation=presentation,
                uploaded_file=uploaded_file,
                filename=getattr(uploaded_file, "name", ""),
            )
        except InvalidImageError as exc:
            return Response(
                {"detail": str(exc)},
                status=status.HTTP_400_BAD_REQUEST,
            )

        return Response(
            ProductPresentationSerializer(updated, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )
