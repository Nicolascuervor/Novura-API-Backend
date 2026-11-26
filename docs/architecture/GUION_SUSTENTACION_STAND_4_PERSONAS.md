# Guion de Presentación en Stand y Sustentación Final por Indicadores de Rúbrica Institucional (5 Expositores): Plataforma Colaborativa Pricecol (Nuvora)

**Presentado por:**  
Alzate Berrio, Samuel  
Arias Lemus, Isabella  
Cuervo Ríos, Nicolás  
Giraldo Espinosa, Maria Victoria  
Hoyos Escobar, Valentina  

**C.U.E. Alexander von Humboldt**  
Facultad de ingenierías y ciencias básicas  
Programa: Ingeniería de software  
Seminario Nuclear IV: Arquitectura de Software II y Modelos de Calidad  
**Docente:** Rubén Darío Díaz Bautista  
Armenia/Quindío — 2026  

---

## 1. Alineación con la Rúbrica Institucional y Diferencial Competitivo

### 1.1 Propósito comunicativo y participación equitativa de los cinco integrantes
El presente documento estructura el guion oficial de sustentación y atención en stand para el proyecto integrador *Pricecol (Nuvora)*, desarrollado en el marco del Seminario Nuclear IV de las asignaturas Arquitectura de Software II y Modelos de Calidad. El discurso ha sido redactado empleando un lenguaje natural, claro y cercano a la experiencia cotidiana de los habitantes de Armenia y el departamento del Quindío, de modo que cualquier visitante de la muestra académica comprenda de inmediato el problema social y económico que resuelve la plataforma.

Simultáneamente, la presentación distribuye el tiempo y el dominio temático de manera **equitativa entre los cinco integrantes del equipo** (**Isabella Arias, Samuel Alzate, María Victoria Giraldo, Nicolás Cuervo y Valentina Hoyos**, con intervenciones de 2.2 a 2.8 minutos cada uno), cubriendo el 100 % de los cuatro indicadores establecidos en el formato institucional de rúbrica de evaluación (25 % por cada indicador) y asignando a cada estudiante el área técnica que lideró durante el semestre.

### 1.2 Nuestro punto fuerte como empresa y aplicación: Calidad y Seguridad de los Datos
Atendiendo la recomendación formulada por el docente evaluador, el eje transversal de la sustentación resalta la **calidad y la seguridad de los datos como el punto fuerte y principal ventaja competitiva de Pricecol (Nuvora)** como empresa y como aplicación tecnológica. En el ecosistema digital actual, cualquier desarrollo básico puede almacenar y mostrar un listado de precios; sin embargo, en una plataforma colaborativa donde convergen ciudadanos reportantes y comercios con intereses propios, la aplicación pierde toda credibilidad si el consumidor sospecha que un precio es falso, está desactualizado, fue manipulado mediante pago publicitario o pone en riesgo su privacidad personal.

Por consiguiente, la identidad empresarial de *Pricecol (Nuvora)* se fundamenta en una promesa de valor verificable: la plataforma no comercializa posiciones en el listado ni actúa como intermediaria de ventas, sino que entrega inteligencia de precios verificada, neutral y protegida. Este punto fuerte se materializa en cuatro pilares de ingeniería explicados a lo largo de las cinco intervenciones:
1. **Veracidad y blindaje antifraude determinista (ISO/IEC 25012):** Motor de validación de cuatro capas que normaliza unidades a gramo o mililitro, calcula vigencia diferenciada por categoría y bloquea precios falsos, errores de digitación o ataques coordinados de competidores antes de que contaminen la comparación o las gráficas históricas.
2. **Seguridad informática y privacidad por diseño (Ley 1581 de 2012 y OWASP):** Limpieza forense en memoria RAM que elimina automáticamente las coordenadas GPS y los metadatos EXIF del teléfono en cada fotografía de evidencia subida por los ciudadanos, complementada con inspección de firmas binarias reales (*magic bytes*) para rechazar archivos maliciosos.
3. **Neutralidad algorítmica incorruptible (Ley 1480 de 2011):** Separación estructural entre el ordenamiento matemático por precio por unidad base y el módulo de promociones comerciales, garantizando en el 100 % de los casos que ningún comercio pueda alterar su posición orgánica.
4. **Aseguramiento automatizado en el ciclo de entrega (DevSecOps):** Barrera continua respaldada por 55 pruebas automatizadas TDD (`96.32 %` de cobertura en el núcleo del dominio), análisis estático de vulnerabilidades SAST con Bandit y Ruff, detección de secretos expuestos y auditoría de contenedores con Aqua Trivy.

### 1.3 Distribución equitativa de indicadores de la rúbrica entre los cinco expositores

| Expositor (Tiempo) | Indicador de la rúbrica institucional cubierto | Síntesis en lenguaje natural (Énfasis en Calidad y Seguridad de Datos) | Apoyo visual en pantalla |
| :--- | :--- | :--- | :--- |
| **Expositor 1: Isabella Arias** (~2.3 min) | **Indicador 1 (25 %):** Presentación e introducción (presentación del stand, problemática y diagnóstico situacional). | Bienvenida al stand, problemática del costo del mercado en Armenia y presentación de nuestro **punto fuerte como empresa: la calidad y seguridad de los datos**. | Interfaz principal de Pricecol con directorio de tiendas y sello de datos verificados. |
| **Expositor 2: Samuel Alzate** (~2.3 min) | **Indicador 2 — Parte A (12.5 %):** Apropiación del conocimiento en Arquitectura de Software (decisiones estructurales y velocidad). | Cómo diseñamos una arquitectura veloz y económica (**Monolito Modular** + **memoria rápida versionada en Redis** + datos iniciales **SIPSA-DANE**) para servir datos frescos en $<0.1\text{ s}$. | Diagrama estructural simplificado / Vista de velocidad de respuesta y actualización instantánea de precios. |
| **Expositor 3: María Victoria Giraldo** (~2.5 min) | **Indicador 2 — Parte B (12.5 %):** Apropiación del conocimiento en Modelos de Calidad y Seguridad de Datos (ISO 25010 e ISO 25012). | Las **4 barreras de calidad y seguridad del dato**: exactitud por gramo/mililitro, vigencia dinámica por categoría, escudo antifraude de 4 niveles y borrado forense de GPS/EXIF en fotos (Ley 1581). | Ficha de producto mostrando precio por unidad base (`$/g`), vigencia, sello antifraude y carriles oficial vs. ciudadano. |
| **Expositor 4: Nicolás Cuervo** (~2.7 min) | **Indicador 3 (25 %):** Resultados logrados (demostración funcional en vivo, pruebas TDD y entrega continua CI/CD). | **Demostración en vivo** del comparador neutral, historial de 90 días blindado contra fraude (`A2`) y guardián automático de seguridad y calidad en GitHub Actions (`B2`: TDD, Bandit, Trivy, k6). | Aplicación en ejecución, gráfica de tendencia de 90 días y pipeline de seguridad y calidad en verde. |
| **Expositor 5: Valentina Hoyos** (~2.3 min) | **Indicador 4 (25 %):** Capacidad de análisis (evaluación ATAM/ISO 25040, evolución, impacto y conclusiones). | Cómo aislar la calidad y seguridad del dato permitió evolucionar sin romper el núcleo (`M-09 = 0.00`), contraste 18 h estimadas vs. 17 h reales, autocrítica CMMI e impacto regional. | Tabla comparativa de esfuerzo estimado vs. real y métricas de evaluación ISO/IEC 25040. |

---

## 2. Guion Estructurado para Cinco Expositores

### 2.1 Expositor 1 (Isabella Arias): Presentación del stand, problemática, diagnóstico situacional y diferencial empresarial (Indicador 1 — 25 %)
**Tiempo estimado:** 2 minutos y 20 segundos.  
**Recurso en pantalla:** Vista principal de la plataforma mostrando establecimientos comerciales de Armenia y productos básicos de la canasta familiar.

#### Apertura y bienvenida al stand
> «Buenas tardes y bienvenidos a nuestro stand. Nuestro equipo está conformado por Samuel Alzate, María Victoria Giraldo, Nicolás Cuervo, Valentina Hoyos y quien les habla, Isabella Arias, estudiantes de sexto semestre de Ingeniería de Software. Hoy queremos presentarles Pricecol (Nuvora), una plataforma tecnológica y colaborativa diseñada para ayudar a las familias de Armenia y del departamento del Quindío a cuidar su presupuesto al momento de hacer mercado».

#### Descripción de la problemática regional y diagnóstico situacional
> «Para comprender por qué surge Pricecol, basta pensar en una situación cotidiana que vivimos en cualquier hogar quindiano cada quincena: salimos a comprar productos básicos como arroz, leche, aceite o huevos, y después de pagar descubrimos que a pocas cuadras, en una tienda de barrio o en otro supermercado, ese mismo artículo costaba un veinte o un treinta por ciento menos.
>
> Al realizar nuestro diagnóstico situacional en Armenia identificamos que esta falta de información transparente afecta a dos actores fundamentales. En primer lugar, golpea el bolsillo de los hogares —especialmente de aquellos donde cualquier ahorro pesa en el presupuesto mensual—, quienes hoy compran a ciegas o pierden tiempo recorriendo varios establecimientos. En segundo lugar, deja en desventaja a las tiendas de barrio y minimercados locales: aunque muchas veces ofrecen mejores precios que las grandes cadenas, carecen de presupuesto publicitario o de canales digitales para que sus vecinos lo sepan».

#### Nuestro punto fuerte como empresa y aplicación: la calidad y seguridad de los datos
> «Frente a esta realidad creamos Pricecol, que funciona como un "Waze de los precios del mercado" donde tanto los ciudadanos como los comercios locales registran y consultan precios reales. Y aquí quiero destacar desde el inicio cuál es nuestro verdadero punto fuerte como empresa y como aplicación: la calidad y la seguridad de los datos.
>
> Sabemos que cualquier página web puede publicar una lista de precios; pero si una familia entra y encuentra precios falsos, vencidos o manipulados por publicidad, o si siente que al subir una foto están exponiendo su ubicación personal, la plataforma pierde toda su credibilidad en cuestión de días. Por eso, en Pricecol unimos Arquitectura de Software II y Modelos de Calidad para construir un blindaje completo que garantiza que cada dato sea auténtico, neutral, vigente y seguro. A continuación, mi compañero Samuel les explicará cómo diseñamos la arquitectura para lograrlo».

---

### 2.2 Expositor 2 (Samuel Alzate): Apropiación del conocimiento en Arquitectura de Software — Eficiencia, Memoria Rápida y Transparencia (Indicador 2, Parte A — 12.5 %)
**Tiempo estimado:** 2 minutos y 20 segundos.  
**Recurso en pantalla:** Esquema visual de la arquitectura Monolito Modular con Redis y vista de comparación mostrando los carriles diferenciados entre el precio oficial del comercio y el consenso ciudadano.

#### Arquitectura pensada para la realidad local y bajo costo operativo
> «Muchas gracias, Isabella. Para que esa promesa de calidad y seguridad funcione en la vida real sin requerir servidores costosos, tomamos decisiones arquitectónicas muy precisas que documentamos en catorce registros de decisión (ADRs). En lugar de dividir el sistema en decenas de microservicios que agotarían los recursos, construimos un Monolito Modular con un núcleo de reglas de negocio completamente independiente, capaz de operar con total estabilidad en un servidor en la nube de muy bajo costo con apenas un gigabyte de memoria RAM.
>
> Además, resolvimos el problema de cómo arrancar la plataforma antes de tener miles de usuarios alimentando el catálogo inicial con referencias públicas del sistema SIPSA del DANE para la ciudad de Armenia, asegurando que desde el primer día el consumidor tenga puntos de referencia confiables».

#### Velocidad instantánea con memoria versionada y coexistencia transparente
> «El segundo reto arquitectónico fue la velocidad y la actualidad del dato. En un comparador de precios, por cada persona que reporta un precio nuevo hay cerca de veinte personas consultando. Para que cientos de personas puedan comparar precios al mismo tiempo en un fin de semana de quincena sin congestionar la base de datos, incorporamos una capa de memoria ultrarrápida en Redis con control inteligente de versiones.
>
> De esta manera, el sistema entrega cualquier comparación en menos de una décima de segundo; y apenas un tendero o un ciudadano reporta un cambio de precio, el número de versión del producto se actualiza en cinco milisegundos para que nadie vea precios viejos. Asimismo, diseñamos la arquitectura para que nunca exista conflicto entre el comercio y la gente: cuando una tienda publica su precio oficial y los ciudadanos reportan otro distinto, no borramos ninguno, sino que mostramos ambos en carriles separados para que haya transparencia total. Ahora mi compañera María Victoria les explicará cómo nuestro modelo de calidad blinda la veracidad y la seguridad de cada dato».

---

### 2.3 Expositor 3 (María Victoria Giraldo): Apropiación del conocimiento en Modelos de Calidad — Las Cuatro Barreras de Calidad y Seguridad del Dato (Indicador 2, Parte B — 12.5 %)
**Tiempo estimado:** 2 minutos y 30 segundos.  
**Recurso en pantalla:** Ficha detallada de un producto donde se aprecia la conversión a precio por unidad base (`$/g`, `$/ml`), la etiqueta de vigencia por categoría y el sello de verificación antifraude y privacidad.

#### Aplicación de los estándares ISO/IEC 25010 e ISO/IEC 25012 al núcleo del negocio
> «Muchas gracias, Samuel. Como mencionamos al inicio, nuestro mayor diferencial competitivo como empresa y aplicación es la calidad y la seguridad de los datos. Desde la asignatura Modelos de Calidad entendimos que de nada sirve un software veloz si la información que entrega es engañosa. Por ello articulamos la norma ISO/IEC 25010:2023 para la calidad del producto con la norma internacional ISO/IEC 25012 para la calidad de los datos, programando cuatro barreras automáticas que todo reporte debe superar antes de llegar a los ojos del consumidor:
>
> La primera barrera es la exactitud matemática por unidad de medida. En el comercio es habitual encontrar una bolsa de arroz de 450 gramos que aparenta ser más barata que otra de 500 gramos. Nuestro motor convierte automáticamente cualquier presentación —ya venga en libras, gramos, litros o centímetros cúbicos— a su unidad base estándar de precio por cada gramo o mililitro, revelando cuál opción representa un ahorro real.
>
> La segunda barrera es la vigencia inteligente según la categoría del producto. Sabemos que el precio de una verdura o de unos huevos cambia mucho más rápido que el de un detergente. Por eso el sistema asigna ventanas de validez diferenciadas —dos días para alimentos perecederos, siete días para abarrotes y catorce días para productos de aseo— e informa al comprador qué tan fresco es cada dato».

#### Escudo antifraude de cuatro niveles y privacidad forense por diseño
> «La tercera barrera es nuestro escudo antifraude de cuatro niveles contra errores o sabotajes. Si alguien digita mal un número o si un competidor intenta perjudicar a la tienda vecina subiendo precios falsos, el sistema compara estadísticamente el reporte contra el comportamiento del mercado. Cuando detecta una desviación superior al treinta y cinco por ciento, evalúa la reputación histórica del usuario, verifica si adjuntó fotografía de respaldo y bloquea envíos repetitivos en ráfaga, aislando cualquier dato no confiable.
>
> Y la cuarta barrera es la seguridad informática y la privacidad por diseño bajo la Ley 1581. Cuando un ciudadano toma una foto del precio en la estantería con su celular, ese archivo trae ocultas la coordenada GPS exacta donde se encuentra y el modelo de su teléfono. Nuestro servidor valida primero la firma binaria interna del archivo para impedir que alguien suba virus disfrazados de imágenes y, acto seguido, borra automáticamente en memoria RAM todos los datos GPS y metadatos EXIF antes de guardar la foto, protegiendo al cien por ciento la ubicación y seguridad de nuestros usuarios. A continuación, Nicolás les mostrará este sistema y nuestros controles automáticos operando en vivo».

---

### 2.4 Expositor 4 (Nicolás Cuervo): Resultados logrados — Demostración Funcional en Vivo y Guardián Automático de Seguridad y Calidad (Indicador 3 — 25 %)
**Tiempo estimado:** 2 minutos y 45 segundos.  
**Recurso en pantalla:** Demostración en tiempo real del comparador y módulo comercial, gráfica de historial de precios de 90 días y panel de GitHub Actions con el pipeline de seguridad y calidad en verde.

#### Demostración en vivo del comparador neutral y del historial de noventa días (Ampliación A2)
> «Gracias, María Victoria. Vamos a comprobar cómo ese punto fuerte en calidad y seguridad de los datos se ve reflejado directamente sobre el sistema en funcionamiento. Aquí tenemos activos nuestro servidor principal y el procesador de tareas conectado a la memoria rápida.
>
> Al buscar un producto de la canasta familiar en Armenia, vemos cómo la lista de establecimientos se ordena única y exclusivamente del menor al mayor costo por gramo o mililitro. Y cuando observamos el módulo comercial —donde las tiendas publican promociones como dos por uno o descuentos porcentuales—, verificamos una regla ética y técnica innegociable bajo la Ley 1480: ninguna promoción puede pagar para comprar el primer puesto; todas se distinguen claramente con su etiqueta promocional sin alterar el ranking natural.
>
> Además, para esta entrega final incorporamos el módulo de historial y tendencia de precios de los últimos noventa días, que ven en esta gráfica. Cuando un comprador quiere saber si una oferta es real o si el precio fue inflado el día anterior, nuestra base de datos —que funciona bajo una política de seguridad de solo inserción donde ningún precio histórico puede ser borrado ni modificado hacia atrás— dibuja la evolución diaria comparando varias tiendas al mismo tiempo, calcula el porcentaje de variación trimestral y expulsa en el cien por ciento de los casos los reportes marcados como fraudulentos por el motor antifraude para que nadie pueda distorsionar la gráfica».

#### Aseguramiento automatizado en el código: TDD, Bandit, Trivy y CI/CD (Ampliación B2)
> «Finalmente, para garantizar que la seguridad de los datos esté respaldada por la seguridad de nuestro propio código, aplicamos dos controles de ingeniería en el desarrollo:
>
> Primero, programamos todas las reglas de negocio mediante Desarrollo Guiado por Pruebas (TDD), completando cincuenta y cinco pruebas automatizadas que cubren el 96.32 % del núcleo del dominio, incluidas pruebas específicas de ciberseguridad y limpieza forense de imágenes.
>
> Segundo, construimos este canal de Entrega Continua con controles de calidad y seguridad bloqueantes en GitHub Actions que ven en pantalla en color verde. Cada vez que subimos un cambio, un guardián automático ejecuta cuatro aduanas: verifica que no existan contraseñas ni llaves expuestas, audita la seguridad del código con Bandit y Ruff, corre las cincuenta y cinco pruebas TDD, escanea el contenedor contra vulnerabilidades críticas con Aqua Trivy y despliega desde cero un servidor de ensayo donde simula tráfico de compradores reales con k6. En nuestra primera ejecución de control demostramos cómo este filtro bloqueó automáticamente un archivo con permisos inadecuados antes de avanzar. Y si alguna vez se requiere revertir una versión en producción, nuestro script automatizado lo hace en menos de noventa segundos sin comprometer un solo dato. Le doy paso a Valentina para cerrar con el análisis de evolución y el impacto del proyecto».

---

### 2.5 Expositor 5 (Valentina Hoyos): Capacidad de análisis, evolución arquitectónica, impacto y conclusiones (Indicador 4 — 25 %)
**Tiempo estimado:** 2 minutos y 20 segundos.  
**Recurso en pantalla:** Cuadro sintético de evaluación arquitectónica e ISO/IEC 25040 (índice de modificación del núcleo igual a 0.00 y comparación entre las 18.0 horas estimadas y las 17.0 horas reales).

#### Cómo nuestro enfoque en calidad y seguridad facilitó la evolución del sistema
> «Muchas gracias, Nicolás. En ingeniería de software, la prueba definitiva para saber si una aplicación tiene cimientos sólidos es evaluar qué sucede cuando el proyecto crece y debemos incorporarle nuevas capacidades meses después.
>
> Al evaluar nuestro sistema aplicando el estándar internacional ISO/IEC 25040 y el método de evaluación arquitectónica basada en escenarios (ATAM), comprobamos que haber concentrado la calidad y la seguridad de los datos en un núcleo independiente fue nuestra decisión estratégica más acertada. Al integrar en esta fase final el módulo comercial, el historial de noventa días y el canal automatizado de entrega continua, obtuvimos un índice de impacto destructivo de cero (0.00) sobre el núcleo original: no tuvimos que reescribir ni alterar ninguna de las reglas de validación y seguridad que ya protegían a la plataforma.
>
> De igual manera, al contrastar nuestra planeación con el trabajo real, antes de programar las ampliaciones finales estimamos un esfuerzo de dieciocho horas y, al medir el tiempo real invertido, cerramos en diecisiete horas, con una desviación de apenas el 5.6 %. Como nuestra arquitectura ya conservaba cada reporte de precio de manera inmutable y auditada, desarrollar el historial de noventa días tomó menos tiempo del previsto, mientras que el principal aprendizaje técnico en el despliegue consistió en homologar los contenedores y controles de seguridad entre nuestros computadores locales en Windows y los servidores Linux en la nube».

#### Reflexión sobre el proceso (CMMI), impacto regional y cierre
> «Al reflexionar sobre nuestro proceso de trabajo tomando como referencia modelos de madurez como CMMI, confirmamos que la calidad y la seguridad de los datos no son revisiones de último momento, sino el pilar que sostiene la confianza ciudadana en un producto digital. Si hoy iniciáramos el proyecto nuevamente, activaríamos los escáneres automáticos de seguridad en entorno Linux desde la primera semana del semestre; y como línea de evolución futura, la arquitectura ya dispone de los puntos de extensión seguros para enviar alertas personalizadas cuando un producto básico baje de precio cerca del hogar del consumidor.
>
> En conclusión, Pricecol (Nuvora) demuestra que cuando una empresa y su aplicación hacen de la calidad, la neutralidad y la seguridad de los datos su mayor punto fuerte, logran un impacto social y económico tangible en nuestra región: proteger el poder adquisitivo de las familias del Quindío con información verídica y brindar a las tiendas de barrio una vitrina digital justa, segura y transparente. Muchas gracias por su visita; quedamos los cinco atentos a sus preguntas o a realizar cualquier consulta en vivo sobre la plataforma».

---

## 3. Intervención Breve de Sesenta Segundos para Visitantes del Stand

> «Bienvenido a Pricecol (Nuvora), el "Waze de los precios del mercado" para Armenia y el Quindío. Es una plataforma web donde tanto los ciudadanos como las tiendas de barrio comparten y comparan precios reales de la canasta familiar para ahorrar dinero al mercar.
>
> Nuestro gran punto fuerte como empresa y como aplicación es la calidad y la seguridad de los datos, porque sabemos que nadie usa un comparador si desconfía de la información. Por eso tenemos tres sellos únicos: primero, calculamos el precio exacto por cada gramo o mililitro para que nadie caiga en trampas de empaques más pequeños; segundo, protegemos tu seguridad con un escudo antifraude que bloquea precios falsos y borra automáticamente la ubicación GPS de las fotos que subes; y tercero, mostramos la gráfica de los últimos noventa días libre de manipulaciones para comprobar si un descuento es real o si fue inflado el día anterior. Si gusta, podemos buscar un producto en vivo aquí en la pantalla».

---

## 4. Matriz de Respuesta para la Ronda de Preguntas del Docente (Distribución para los 5 Integrantes)

| Pregunta de evaluación (Responsable sugerido) | Respuesta argumentada (Explicación clara + Evidencia técnica del proyecto) |
| :--- | :--- |
| **1. ¿Cuál es el punto fuerte o ventaja competitiva de Pricecol (Nuvora) como empresa y aplicación?** *(Responde: Isabella Arias o María Victoria Giraldo)* | Nuestro punto fuerte es la calidad, neutralidad y seguridad de los datos colaborativos. Mientras un catálogo convencional solo almacena precios sin validarlos, Pricecol aplica un blindaje integral gobernado por ISO/IEC 25012, la Ley 1581 y controles OWASP: normaliza cada producto a su unidad base (`$/g`, `$/ml`), aplica vigencia dinámica por categoría, filtra sabotajes mediante un motor antifraude de cuatro capas, impide que las promociones compren posición en el listado y sanitiza en memoria RAM los metadatos EXIF/GPS y las firmas binarias de cada fotografía ciudadana. |
| **2. ¿Por qué eligieron un Monolito Modular y cómo logran actualización inmediata con caché en Redis (`EC-02`)?** *(Responde: Samuel Alzate)* | En un servidor económico de 1 GB de RAM (instancia `e2-micro`), dividir el sistema en microservicios agotaría la memoria en sobrecarga de red. Con un Monolito Modular (`ADR-01`) mantenemos las reglas de negocio aisladas en `core_domain` con latencia interna nula. Y para la caché en Redis aplicamos versionamiento atómico de claves (`ADR-02` y `ADR-10`): cada vez que entra un reporte o cambio oficial del comercio, la versión del producto sube en menos de 5 milisegundos, sirviendo el dato fresco al instante. |
| **3. ¿Cómo se articulan los estándares ISO/IEC 25010, 25012 y la Ley 1581 para proteger al consumidor?** *(Responde: María Victoria Giraldo)* | ISO/IEC 25010:2023 gobierna la calidad del software (velocidad, capacidad de interacción, integridad y mantenibilidad), mientras que ISO/IEC 25012 asegura las dimensiones críticas del dato colaborativo: exactitud mediante el `UnitNormalizer`, actualidad con la `ValidityPolicy` y credibilidad con el `AnomalyDetector` de cuatro capas. A su vez, cumplimos la Ley 1581 eliminando coordenadas GPS/EXIF en memoria RAM antes de escribir cualquier imagen en disco (`ADR-12`). |
| **4. ¿Por qué descartaron Event Sourcing para el historial de 90 días y cómo probaron que el Quality Gate bloquea defectos?** *(Responde: Nicolás Cuervo)* | Descartamos Event Sourcing (`ADR-13`) porque un reporte de precio en góndola ya es un hecho histórico inmutable; una tabla relacional *Append-Only* con índices compuestos y exclusión del 100 % de reportes `ANOMALOUS` genera la gráfica multi-tienda de 90 días en menos de 15 milisegundos. Respecto al Quality Gate (`ADR-14`), en la corrida `Run #1` de GitHub Actions el verificador detectó el hallazgo `EXE001` en `manage.py` y bloqueó automáticamente el despliegue; tras remediarlo y pasar las 55 pruebas TDD (`96.32 %`), Bandit, Trivy y k6, el flujo quedó 100 % en verde (`Run #4`). |
| **5. ¿Qué demostró el contraste entre el esfuerzo estimado y el real al evolucionar la arquitectura en el Corte 3?** *(Responde: Valentina Hoyos)* | Antes de programar (commit `1b1cb51`) estimamos 18.0 horas para las ampliaciones `A2` y `B2`, y al cierre real invertimos 17.0 horas (`-5.6 %` de desviación), manteniendo un índice de impacto destructivo `M-09 = 0.00` sobre el núcleo. Esto demostró conforme a ISO/IEC 25040 y ATAM que desacoplar el núcleo de calidad y seguridad ahorra esfuerzo al agregar nuevas funciones, concentrando el aprendizaje en la paridad operativa entre entornos locales Windows y contenedores Linux. |
