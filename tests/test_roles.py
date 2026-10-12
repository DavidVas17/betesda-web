"""Política de acceso por rol: administración técnica, matriz del panel y reglas finas."""

from datetime import timedelta

import pytest
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse
from django.utils import timezone

from apps.accounts.roles import (
    CARE,
    CHURCH_ADMIN,
    COLLABORATOR,
    COORDINATOR,
    GALLERY,
    READ_ONLY,
    ROLES,
    role_permission_codenames,
    set_user_roles,
)
from apps.contacts.models import ContactMessage
from apps.events.models import Event
from apps.gallery.models import Album
from apps.news.models import Post

User = get_user_model()


def member(username, *roles, **extra):
    user = User.objects.create_user(
        username=username, password="Betesda-Roles-2026!", is_staff=True, **extra
    )
    set_user_roles(user, [role.name for role in roles])
    return user


def make_event(**overrides):
    data = {
        "title": "Culto familiar",
        "summary": "Un tiempo para compartir",
        "description": "Alabanza y enseñanza.",
        "starts_at": timezone.now() + timedelta(days=3),
        "location": "Templo principal",
    }
    data.update(overrides)
    return Event.objects.create(**data)


def event_form(**overrides):
    data = {
        "title": "Vigilia de oración",
        "summary": "Oramos juntos",
        "description": "Una noche de oración por la comunidad.",
        "starts_at": "2028-11-15T19:00",
        "ends_at": "2028-11-15T22:00",
        "location": "Templo principal",
    }
    data.update(overrides)
    return data


def post_form(**overrides):
    data = {
        "title": "Anuncio importante",
        "excerpt": "Información para las familias",
        "body": "Compartimos esta noticia con la iglesia.",
    }
    data.update(overrides)
    return data


@pytest.fixture
def content(db):
    author = User.objects.create_user(username="autor", is_staff=True)
    return {
        "event": make_event(is_published=True),
        "post": Post.objects.create(
            title="Noticia", excerpt="Resumen", body="Texto", author=author
        ),
        "album": Album.objects.create(title="Retiro", is_published=True),
        "message": ContactMessage.objects.create(
            name="Persona",
            email="persona@example.com",
            subject="Petición",
            message="Oren por mi familia.",
            kind=ContactMessage.Kind.PRAYER,
        ),
    }


# --- Definición de roles ------------------------------------------------------------


@pytest.mark.django_db
def test_every_role_permission_exists():
    """Un permiso mal escrito en roles.py se quedaría en silencio sin efecto."""
    existing = {
        f"{app}.{codename}"
        for app, codename in Permission.objects.values_list("content_type__app_label", "codename")
    }
    for role in ROLES:
        missing = role_permission_codenames(role) - existing
        assert not missing, f"{role.name}: {sorted(missing)}"


@pytest.mark.django_db
def test_migrate_leaves_each_role_group_with_its_exact_permissions():
    for role in ROLES:
        group = Group.objects.get(name=role.name)
        granted = {
            f"{app}.{codename}"
            for app, codename in group.permissions.values_list(
                "content_type__app_label", "codename"
            )
        }
        assert granted == role_permission_codenames(role)


# --- Administración técnica -----------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize("role", ROLES, ids=lambda role: role.key)
def test_no_panel_role_reaches_technical_admin(client, role):
    client.force_login(member(f"admin-{role.key}", role))

    for url in (
        reverse("admin:index"),
        reverse("admin:events_event_changelist"),
        reverse("admin:accounts_user_changelist"),
        reverse("admin:contacts_contactmessage_changelist"),
    ):
        response = client.get(url)
        assert response.status_code == 302
        assert response.url.startswith(reverse("admin:login"))


@pytest.mark.django_db
def test_superuser_reaches_technical_admin_and_sees_its_link(admin_client):
    assert admin_client.get(reverse("admin:index")).status_code == 200
    content = admin_client.get(reverse("panel:dashboard")).content.decode()
    assert "Administración técnica" in content


@pytest.mark.django_db
def test_team_panel_does_not_link_to_technical_admin(client):
    client.force_login(member("admin-iglesia", CHURCH_ADMIN))

    assert "Administración técnica" not in client.get(reverse("panel:dashboard")).content.decode()


# --- Matriz del panel -------------------------------------------------------------------

OK, NO = 200, 403
# Columnas: Admin. iglesia, Coordinación, Colaboración, Galería, Atención, Solo lectura
MATRIX_ROLES = (CHURCH_ADMIN, COORDINATOR, COLLABORATOR, GALLERY, CARE, READ_ONLY)
MATRIX = {
    "event_list": (OK, OK, OK, NO, NO, OK),
    "event_create": (OK, OK, OK, NO, NO, NO),
    "news_list": (OK, OK, OK, NO, NO, OK),
    "news_create": (OK, OK, OK, NO, NO, NO),
    "album_list": (OK, OK, OK, OK, NO, OK),
    "album_create": (OK, OK, OK, OK, NO, NO),
    "event_delete": (OK, OK, NO, NO, NO, NO),
    "news_delete": (OK, OK, NO, NO, NO, NO),
    "album_delete": (OK, OK, NO, OK, NO, NO),
    "message_list": (OK, NO, NO, NO, OK, NO),
    "message_detail": (OK, NO, NO, NO, OK, NO),
    "message_export": (OK, NO, NO, NO, NO, NO),
    "message_delete": (OK, NO, NO, NO, NO, NO),
    "settings": (OK, NO, NO, NO, NO, NO),
    "institution": (OK, NO, NO, NO, NO, NO),
    "user_list": (OK, NO, NO, NO, NO, NO),
    "activity": (OK, NO, NO, NO, NO, NO),
    "account": (OK, OK, OK, OK, OK, OK),
    "dashboard": (OK, OK, OK, OK, OK, OK),
}
OBJECT_ARGS = {
    "event_delete": "event",
    "news_delete": "post",
    "album_delete": "album",
    "message_detail": "message",
    "message_delete": "message",
}


@pytest.mark.django_db
@pytest.mark.parametrize("route", MATRIX, ids=str)
def test_panel_matrix(client, content, route):
    for role, expected in zip(MATRIX_ROLES, MATRIX[route], strict=True):
        client.force_login(member(f"matriz-{role.key}-{route}"[:150], role))
        key = OBJECT_ARGS.get(route)
        url = reverse(f"panel:{route}", args=[content[key].pk] if key else [])
        assert client.get(url).status_code == expected, f"{role.name} en {route}"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("role", "route", "obj"),
    [
        (COLLABORATOR, "event_action", "event"),
        (COLLABORATOR, "news_action", "post"),
        (COLLABORATOR, "album_action", "album"),
        (GALLERY, "event_action", "event"),
        (READ_ONLY, "news_action", "post"),
        (CARE, "album_action", "album"),
    ],
)
def test_roles_without_publish_permission_cannot_publish(client, content, role, route, obj):
    client.force_login(member(f"publica-{role.key}", role))
    target = content[obj]

    response = client.post(reverse(f"panel:{route}", args=[target.pk]), {"action": "publish"})

    assert response.status_code == 403


@pytest.mark.django_db
def test_gallery_role_publishes_albums(client, content):
    album = content["album"]
    Album.objects.filter(pk=album.pk).update(is_published=False)
    client.force_login(member("galeria", GALLERY))

    response = client.post(reverse("panel:album_action", args=[album.pk]), {"action": "publish"})

    assert response.status_code == 302
    album.refresh_from_db()
    assert album.is_published is True


@pytest.mark.django_db
def test_roles_combine_their_permissions(client, content):
    client.force_login(member("doble", COLLABORATOR, CARE))

    assert client.get(reverse("panel:event_create")).status_code == OK
    assert client.get(reverse("panel:message_list")).status_code == OK
    assert client.get(reverse("panel:message_export")).status_code == NO


# --- Colaboración: borradores propios ---------------------------------------------------


@pytest.mark.django_db
def test_collaborator_creates_drafts_even_if_publication_fields_are_forged(client):
    author = member("colaboradora", COLLABORATOR)
    client.force_login(author)

    client.post(
        reverse("panel:event_create"),
        event_form(is_published="on", is_featured="on"),
    )
    client.post(
        reverse("panel:news_create"),
        post_form(status=Post.Status.PUBLISHED, is_featured="on"),
    )
    client.post(reverse("panel:album_create"), {"title": "Campamento", "is_published": "on"})

    event = Event.objects.get(title="Vigilia de oración")
    post = Post.objects.get(title="Anuncio importante")
    album = Album.objects.get(title="Campamento")
    assert (event.is_published, event.is_featured, event.created_by) == (False, False, author)
    assert (post.status, post.is_featured, post.author) == (Post.Status.DRAFT, False, author)
    assert (album.is_published, album.created_by) == (False, author)


@pytest.mark.django_db
def test_collaborator_form_hides_publication_fields(client):
    client.force_login(member("colaborador", COLLABORATOR))

    content = client.get(reverse("panel:event_create")).content.decode()

    assert 'name="is_published"' not in content
    assert "Se guardará como borrador" in content


@pytest.mark.django_db
def test_collaborator_edits_own_draft_only(client):
    author = member("autora", COLLABORATOR)
    other = member("otra-persona", COLLABORATOR)
    own = make_event(title="Mi borrador", created_by=author)
    foreign = make_event(title="Ajeno", created_by=other)
    client.force_login(author)

    ok = client.post(reverse("panel:event_edit", args=[own.pk]), event_form(title="Editado"))
    denied = client.post(reverse("panel:event_edit", args=[foreign.pk]), event_form(title="X"))

    assert ok.status_code == 302
    assert denied.status_code == 403
    own.refresh_from_db()
    foreign.refresh_from_db()
    assert own.title == "Editado"
    assert foreign.title == "Ajeno"


@pytest.mark.django_db
def test_collaborator_cannot_change_own_content_once_published(client):
    author = member("autor-publicado", COLLABORATOR)
    published = make_event(title="Ya publicado", created_by=author, is_published=True)
    client.force_login(author)

    page = client.get(reverse("panel:event_edit", args=[published.pk]))
    response = client.post(
        reverse("panel:event_edit", args=[published.pk]), event_form(title="Cambio")
    )

    assert page.status_code == 200
    assert "Detalles de evento" in page.content.decode()
    assert response.status_code == 403
    published.refresh_from_db()
    assert published.title == "Ya publicado"


@pytest.mark.django_db
def test_collaborator_list_offers_edit_only_on_own_drafts(client):
    author = member("lista-colaboradora", COLLABORATOR)
    make_event(title="Propio", created_by=author)
    make_event(title="De otra persona")
    client.force_login(author)

    content = client.get(reverse("panel:event_list")).content.decode()

    assert content.count("Editar</a>") == 1
    assert content.count("Ver</a>") == 1
    assert "Publicar en el sitio" not in content


@pytest.mark.django_db
def test_collaborator_cannot_upload_photos_to_someone_elses_album(client, content):
    client.force_login(member("fotos-ajenas", COLLABORATOR))

    response = client.post(reverse("panel:album_upload", args=[content["album"].pk]), {})

    assert response.status_code == 403


@pytest.mark.django_db
def test_coordinator_reviews_and_publishes_a_collaborator_draft(client):
    author = member("autor-borrador", COLLABORATOR)
    draft = make_event(title="Para revisar", created_by=author)
    client.force_login(member("coordinacion", COORDINATOR))

    response = client.post(reverse("panel:event_action", args=[draft.pk]), {"action": "publish"})

    assert response.status_code == 302
    draft.refresh_from_db()
    assert draft.is_published is True


# --- Atención y oración -----------------------------------------------------------------


@pytest.mark.django_db
def test_care_role_follows_up_but_cannot_export_or_delete(client, content):
    message = content["message"]
    client.force_login(member("oracion", CARE))

    action = client.post(
        reverse("panel:message_action", args=[message.pk]), {"action": "in_progress"}
    )
    delete = client.post(reverse("panel:message_delete", args=[message.pk]))

    assert action.status_code == 302
    assert delete.status_code == 403
    message.refresh_from_db()
    assert message.status == ContactMessage.Status.IN_PROGRESS
    page = client.get(reverse("panel:message_list")).content.decode()
    assert "Exportar CSV" not in page


# --- Gestión del equipo -----------------------------------------------------------------


def team_form(user, **overrides):
    data = {
        "username": user.username,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "email": user.email,
        "is_active": "on",
        "roles": user.role_names,
    }
    data.update(overrides)
    return data


@pytest.mark.django_db
def test_church_admin_assigns_regular_roles(client):
    client.force_login(member("admin-asigna", CHURCH_ADMIN))
    target = member("nuevo-integrante")

    response = client.post(
        reverse("panel:user_edit", args=[target.pk]),
        team_form(target, roles=[COORDINATOR.name, CARE.name]),
    )

    assert response.status_code == 302
    target.refresh_from_db()
    assert target.role_names == [COORDINATOR.name, CARE.name]
    entry = LogEntry.objects.filter(object_id=str(target.pk)).latest("action_time")
    assert COORDINATOR.name in entry.change_message


@pytest.mark.django_db
def test_church_admin_cannot_grant_church_admin(client):
    client.force_login(member("admin-no-eleva", CHURCH_ADMIN))
    target = member("quiere-subir", COORDINATOR)

    response = client.post(
        reverse("panel:user_edit", args=[target.pk]),
        team_form(target, roles=[CHURCH_ADMIN.name]),
    )

    assert response.status_code == 200
    assert "Solo el superadministrador" in response.content.decode()
    target.refresh_from_db()
    assert target.role_names == [COORDINATOR.name]


@pytest.mark.django_db
def test_superuser_grants_church_admin(admin_client):
    target = member("pastor", COORDINATOR)

    response = admin_client.post(
        reverse("panel:user_edit", args=[target.pk]),
        team_form(target, roles=[CHURCH_ADMIN.name]),
    )

    assert response.status_code == 302
    target.refresh_from_db()
    assert target.role_names == [CHURCH_ADMIN.name]


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["user_edit", "user_delete", "user_password"])
def test_church_admin_cannot_manage_a_peer(client, route):
    client.force_login(member("admin-uno", CHURCH_ADMIN))
    peer = member("admin-dos", CHURCH_ADMIN)

    assert client.get(reverse(f"panel:{route}", args=[peer.pk])).status_code == 403
    assert client.post(reverse(f"panel:{route}", args=[peer.pk]), {}).status_code == 403


@pytest.mark.django_db
def test_nobody_changes_their_own_roles_or_deactivates_themselves(client):
    me = member("yo-mismo", CHURCH_ADMIN)
    client.force_login(me)

    response = client.post(
        reverse("panel:user_edit", args=[me.pk]),
        team_form(me, roles=[READ_ONLY.name], is_active="", first_name="Nuevo"),
    )

    assert response.status_code == 302
    me.refresh_from_db()
    assert me.first_name == "Nuevo"
    assert me.role_names == [CHURCH_ADMIN.name]
    assert me.is_active is True


@pytest.mark.django_db
@pytest.mark.parametrize("route", ["user_delete", "user_password"])
def test_own_account_cannot_be_deleted_or_reset_from_team_screen(client, route):
    me = member("sin-autoborrado", CHURCH_ADMIN)
    client.force_login(me)

    assert client.get(reverse(f"panel:{route}", args=[me.pk])).status_code == 403


@pytest.mark.django_db
def test_deactivating_a_member_releases_their_open_requests(client, content):
    message = content["message"]
    helper = member("ayudante", CARE)
    ContactMessage.objects.filter(pk=message.pk).update(
        assigned_to=helper, status=ContactMessage.Status.IN_PROGRESS
    )
    client.force_login(member("admin-desactiva", CHURCH_ADMIN))

    response = client.post(
        reverse("panel:user_edit", args=[helper.pk]), team_form(helper, is_active="")
    )

    assert response.status_code == 302
    message.refresh_from_db()
    assert message.assigned_to is None


@pytest.mark.django_db
def test_team_list_shows_roles(client):
    member("persona-con-roles", COORDINATOR, CARE)
    client.force_login(member("admin-lista", CHURCH_ADMIN))

    content = client.get(reverse("panel:user_list")).content.decode()

    assert f"{COORDINATOR.name}, {CARE.name}" in content


# --- Migración de los roles anteriores --------------------------------------------------


@pytest.mark.django_db(transaction=True)
def test_migration_moves_old_roles_into_the_new_groups():
    executor = MigrationExecutor(connection)
    before = [("accounts", "0001_initial")]
    after = [("accounts", "0002_roles_como_grupos")]
    executor.migrate(before)
    old_apps = executor.loader.project_state(before).apps
    OldUser = old_apps.get_model("accounts", "User")
    OldGroup = old_apps.get_model("auth", "Group")
    old_editors = OldGroup.objects.create(name="Editores de contenido")
    admin = OldUser.objects.create(username="antes-admin", role="ADMIN", is_staff=True)
    editor = OldUser.objects.create(username="antes-editor", role="EDITOR", is_staff=True)
    editor.groups.add(old_editors)

    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(after)
    executor = MigrationExecutor(connection)
    executor.loader.build_graph()
    executor.migrate(executor.loader.graph.leaf_nodes())

    assert User.objects.get(pk=admin.pk).role_names == [CHURCH_ADMIN.name]
    assert User.objects.get(pk=editor.pk).role_names == [COORDINATOR.name]
    assert not Group.objects.filter(name="Editores de contenido").exists()


@pytest.mark.django_db
def test_requests_can_only_be_assigned_to_people_who_can_read_them(admin_client, content):
    message = content["message"]
    reader = member("lectora-oracion", CARE)
    outsider = member("solo-fotos", GALLERY)
    url = reverse("panel:message_detail", args=[message.pk])

    page = admin_client.get(url).content.decode()
    denied = admin_client.post(
        url, {"status": "IN_PROGRESS", "assigned_to": str(outsider.pk), "internal_notes": ""}
    )
    allowed = admin_client.post(
        url, {"status": "IN_PROGRESS", "assigned_to": str(reader.pk), "internal_notes": ""}
    )

    assert "lectora-oracion" in page
    assert "solo-fotos" not in page
    assert denied.status_code == 200
    assert allowed.status_code == 302
    message.refresh_from_db()
    assert message.assigned_to == reader
