"""Valores por defecto de la información institucional (documento del proyecto, págs. 2–5).

Se usan mientras la configuración del sitio no tenga su propio texto. Los ministerios y los
valores viven en la base de datos (modelos ``Ministry`` y ``ChurchValue``) y se editan
desde el panel.
"""

INSTITUTION = {
    "name": "Ministerios Pentecostés Betesda Rosa de Sarón",
    "slogan": "Amando a Dios, unidos en Cristo y sirviendo a nuestra comunidad.",
    "founded": 2006,
    "address": "13 calle 13-02, colonia Santa Isabel II, proyectos, zona 3 de Villa Nueva.",
    "phone": "4171-3008",
    "email": "",
    "facebook_url": "https://www.facebook.com/profile.php?id=100074415457773",
    "map_url": "https://maps.app.goo.gl/sSZMK48Ky8Mg1jSH6?g_st=iw",
    "map_cid": "6810111933317615033",
    "mission": (
        "Predicar el evangelio de Jesucristo, formando discípulos mediante la enseñanza de "
        "la Palabra de Dios, el amor, la unidad y el trabajo en equipo; sirviendo integralmente "
        "a niños, jóvenes, adultos y adultos mayores, y llevando esperanza, orientación "
        "y ayuda a la comunidad."
    ),
    "vision": (
        "Ser una iglesia que transforma vidas por medio del amor de Cristo, formando familias "
        "y generaciones comprometidas con Dios, unidas en la fe y dispuestas a servir "
        "y transformar positivamente a la comunidad."
    ),
    "purpose": (
        "Glorificar a Dios y extender Su Reino llevando el amor de Cristo a las personas, "
        "formando discípulos y sirviendo a la comunidad para contribuir a la transformación "
        "espiritual, familiar y social del entorno."
    ),
    "history": (
        "Ministerios Pentecostés Betesda Rosa de Sarón fue fundada en 2006 y ha mantenido "
        "un funcionamiento ininterrumpido desde entonces. A través de sus diferentes "
        "ministerios, la congregación acompaña a niños, jóvenes, adultos y adultos mayores, "
        "y desarrolla su labor de evangelismo, formación cristiana, acción social "
        "y servicio comunitario."
    ),
}
