from .models import ContactMessage

CONTACT_MODES = {
    ContactMessage.Kind.PRAYER: {
        "kind": ContactMessage.Kind.PRAYER,
        "slug": "oracion",
        "tab": "Peticiones de oración",
        "title": "Comparte tu petición de oración",
        "subtitle": "Queremos acompañarte en oración.",
        "left_title": "Oremos juntos",
        "intro": "Comparte con confianza tu petición. Nuestro equipo la recibirá de forma privada.",
        "button": "Enviar petición de oración",
        "success": "Recibimos tu petición de oración. Gracias por confiar en nosotros.",
        "labels": {
            "name": "Tu nombre completo",
            "email": "Correo para acompañarte",
            "phone": "Teléfono para contactarte",
            "subject": "Motivo de la oración",
            "message": "Tu petición de oración",
            "privacy_accepted": (
                "Acepto que el equipo reciba mi petición y use mis datos para contactarme."
            ),
        },
        "placeholders": {
            "name": "¿Cómo te llamas?",
            "email": "tucorreo@ejemplo.com",
            "phone": "+502 4171-3008",
            "subject": "Por ejemplo: oración por mi familia",
            "message": "Cuéntanos por qué te gustaría que oremos.",
        },
        "privacy": (
            "Tu petición y tus datos se comparten únicamente con el equipo de atención. "
            "No se publicarán en el sitio."
        ),
    },
    ContactMessage.Kind.CONTACT: {
        "kind": ContactMessage.Kind.CONTACT,
        "slug": "contacto",
        "tab": "Contáctanos",
        "title": "Envíanos tu mensaje",
        "subtitle": "Estamos aquí para escucharte.",
        "left_title": "Conversemos",
        "intro": (
            "¿Quieres conocer la iglesia, participar en un ministerio o consultar una actividad? "
            "Escríbenos y nuestro equipo te atenderá."
        ),
        "button": "Enviar mensaje",
        "success": "Recibimos tu mensaje. Nuestro equipo te contactará al correo que indicaste.",
        "labels": {
            "name": "Nombre completo",
            "email": "Correo de contacto",
            "phone": "Número de teléfono",
            "subject": "Asunto del mensaje",
            "message": "¿En qué podemos ayudarte?",
            "privacy_accepted": (
                "Acepto que utilicen mis datos para atender este mensaje y contactarme."
            ),
        },
        "placeholders": {
            "name": "Escribe tu nombre completo",
            "email": "tucorreo@ejemplo.com",
            "phone": "+502 4171-3008",
            "subject": "¿Sobre qué quieres conversar?",
            "message": "Escribe tu consulta o mensaje para nuestro equipo.",
        },
        "privacy": (
            "Usaremos tus datos de contacto y tu mensaje para atender tu consulta. "
            "No se publicarán en el sitio."
        ),
    },
}
