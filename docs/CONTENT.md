# Información institucional del sitio

La fuente es `Proyecto_Seminario_Betesda_Rosa_de_Saron_Diseno_Unificado.pdf`, proporcionado por el usuario para adaptar el contenido público. La documentación de gestión, integrantes del proyecto, presupuesto y análisis de instituciones similares no se publica como información de la iglesia.

| Información | Fuente | Ubicación en el sitio |
| --- | --- | --- |
| Nombre, misión, visión, propósito y lema | Página 2 | Inicio, Nosotros y pie de página |
| Diez valores institucionales | Páginas 2–3 | Nosotros |
| Logotipo oficial | Imagen de la página 4 | Menú principal, portada, BackOffice y favicons |
| Fundación en 2006 e historia | Página 4 | Inicio y Nosotros |
| Dirección, teléfono y Facebook | Página 4 | Contacto y pie de página |
| Siete ministerios y sus descripciones | Página 5 | Ministerios y adelanto en Inicio |

El logo se conserva como `static/images/logo-betesda.jpg`, extraído del PDF sin cambiar el diseño. Los textos institucionales están centralizados en `apps/core/content.py`. La configuración del BackOffice prevalece sobre los datos de contacto de referencia cuando contiene valores.

El documento indica que no existe un correo institucional. El sitio no inventa uno: solo muestra correo oficial si se configura en el BackOffice. Tampoco se inventan horarios de servicio, nombres de pastores, eventos, noticias ni fotografías; el contenido dinámico proviene de registros publicados en el panel.

## Páginas públicas

- `/`: portada con misión, información general y adelantos de contenido.
- `/nosotros/`: historia, misión, visión, propósito, lema y valores.
- `/ministerios/`: los siete ministerios de la institución.
- `/eventos/`: próximas actividades y actividades anteriores; detalles por identificador.
- `/noticias/`: noticias y anuncios publicados; detalles por identificador.
- `/galeria/`: álbumes publicados y fotografías con vista ampliada.
- `/contacto/`: Peticiones de oración / Contáctanos; pestaña inicial de oración.
- `/contacto/?tipo=contacto`: formulario de consultas generales.

Las dos modalidades comparten campos y validaciones. El tipo se almacena en `ContactMessage.kind`; los registros anteriores mantienen la categoría Contacto y su estado original. Las peticiones permanecen privadas y solo se consultan desde el BackOffice con los permisos existentes.

La sección **Noticias y anuncios** permanece visible en Inicio, con un mensaje cuando aún no hay publicaciones. Muestra hasta tres noticias públicas, priorizando las destacadas; los borradores, archivos y publicaciones futuras permanecen ocultos.

Contacto incluye un mapa interactivo de Google Maps del lugar **iglesia rosa de saron**, identificado por el [enlace compartido por el usuario](https://maps.app.goo.gl/sSZMK48Ky8Mg1jSH6?g_st=iw). Su identificador de Google Maps es `6810111933317615033`; se utiliza directamente para señalar el templo. Ese enlace también se utiliza en Inicio y en todos los botones para abrir el mapa o ver cómo llegar.

Un enlace personalizado en **Configuración del sitio** sigue prevaleciendo. Si se configura otra ubicación, el mapa se basa en la dirección configurada. El mapa requiere conexión a Internet y no solicita la ubicación del visitante.

Los favicons ICO, PNG y el icono de Apple se generan del logotipo existente, conservando su diseño. Se comparten entre el sitio público, el panel y su pantalla de acceso.
