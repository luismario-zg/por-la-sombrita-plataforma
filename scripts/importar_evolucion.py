#!/usr/bin/env python3
"""Prepara o importa borradores de evolución sin ejecutarse implícitamente.

Por defecto solo valida los HTML. Para escribir se requieren --apply,
--backup-confirmed y una --database explícita. Nunca marca documentos oficiales.
"""
import argparse
import json
import sqlite3
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from bs4 import BeautifulSoup

from app.core import clean_html, connect, event, now, sections, short_sentence


SOURCE_DIR = BASE / "contenido" / "evolucion"
ATTRIBUTION = "Codex con guía de Luis Mario y conocimiento comunitario al 20 de septiembre de 2026."
REASON = (
    "Importación revisable de contenido de evolución. Conserva estado de propuesta; "
    "no implica ratificación. " + ATTRIBUTION
)
HISTORIC_MANUAL_ANCHORS = {
    "manual-de-operaciones-de-la-comunidad",
    "un-proyecto-abierto-una-responsabilidad-compartida",
    "funciones-y-relevos",
    "antes-durante-y-después-de-una-sesión",
    "decidir-sin-convertir-propuestas-en-acuerdos",
    "gestionar-tareas-y-disponibilidad",
    "investigación-y-publicación-permanente",
    "incorporación-permanencia-y-salida",
    "territorio-cuidados-e-intervención",
    "alianzas-recursos-y-cuentas",
    "documentación-pública-y-resguardo-privado",
    "revisión-del-manual",
}
D07_SECTION = "redes-sociales-autonomia-y-publicacion"
D07_QUOTE = (
    "Como punto de partida para discutir, proponemos no dar prioridad automática a las "
    "reglas de posicionamiento o marketing de cada red: primero deben importar la "
    "pertinencia, la claridad y la posibilidad humana de publicar; después se revisan "
    "alcance, comprensión, respuestas útiles y posibles señales de saturación."
)
D07_TITLE = "¿Qué lugar deben tener las reglas y métricas de las redes sociales?"
ACTIVITY_SEED = {
    "activity_type": "evento",
    "title": "Actividad del 15 de septiembre",
    "description": (
        "Actividad relatada como realizada fuera de LABNL con señalética y volantes de "
        "Por la Sombrita. La descripción detallada y sus resultados requieren contraste."
    ),
    "starts_at": None,
    "ends_at": None,
    "location": "Fuera de LABNL",
    "status": "completed",
    "pending_details": [
        "Confirmar año y horario exacto; la fuente solo refiere el 15 de septiembre por la noche.",
        "Confirmar nombre definitivo y lugar exacto.",
        "Completar descripción, personas participantes autorizadas y evidencia.",
        "Contrastar resultados y aprendizaje antes de publicarlos como conclusión comunitaria.",
    ],
    "source_reference": "A11 01:07–02:06; respuesta de planeación D14 del 21-sep-2026.",
}


def parse_source(path):
    soup = BeautifulSoup(path.read_text(encoding="utf-8"), "html.parser")
    article = soup.select_one("article[data-document-slug]")
    if article is None:
        raise ValueError(f"{path}: falta article[data-document-slug].")
    slug = article.get("data-document-slug", "").strip()
    title = article.get("data-document-title", "").strip()
    intro = article.get("data-document-intro", "").strip()
    status = article.get("data-document-status", "").strip()
    if not slug or not title or not intro or status != "proposal":
        raise ValueError(f"{path}: metadatos incompletos o estado distinto de proposal.")
    if path.stem != slug:
        raise ValueError(f"{path}: el nombre debe coincidir con el slug {slug}.")
    html = clean_html(article.decode_contents())
    parsed_sections = sections(html)
    if not parsed_sections:
        raise ValueError(f"{path}: el documento necesita al menos una sección H2.")
    anchors = {part["id"] for part in parsed_sections}
    if len(anchors) != len(parsed_sections):
        raise ValueError(f"{path}: hay anclas H2 duplicadas.")
    if slug == "manual":
        missing = HISTORIC_MANUAL_ANCHORS - anchors
        if missing:
            raise ValueError(f"{path}: faltan anclas históricas: {sorted(missing)}")
        if D07_SECTION not in anchors:
            raise ValueError(f"{path}: falta la sección necesaria para el hilo D07.")
        d07 = next(part for part in parsed_sections if part["id"] == D07_SECTION)
        if D07_QUOTE not in d07["text"]:
            raise ValueError(f"{path}: cambió la cita prevista para D07.")
    return {
        "slug": slug,
        "title": title,
        "intro": intro,
        "status": status,
        "html": html,
        "sections": parsed_sections,
        "anchors": anchors,
        "source": path,
    }


def load_sources():
    paths = sorted(SOURCE_DIR.glob("*.html"))
    if not paths:
        raise ValueError(f"No hay HTML en {SOURCE_DIR}.")
    documents = [parse_source(path) for path in paths]
    slugs = [document["slug"] for document in documents]
    if len(set(slugs)) != len(slugs):
        raise ValueError("Hay slugs duplicados en contenido/evolucion.")
    return documents


def compare(connection, documents):
    plan = []
    for document in documents:
        current = connection.execute(
            "SELECT * FROM documents WHERE slug=?", (document["slug"],)
        ).fetchone()
        if current is None:
            plan.append(("crear", document, None))
            continue
        if current["hidden"]:
            raise RuntimeError(f"{document['slug']}: el documento existente está oculto.")
        if current["status"] == "official" and current["html"] != document["html"]:
            raise RuntimeError(
                f"{document['slug']}: existe una versión oficial distinta; requiere reconciliación humana."
            )
        if document["slug"] == "manual":
            current_anchors = {part["id"] for part in sections(current["html"])}
            missing = current_anchors - document["anchors"]
            if missing:
                raise RuntimeError(
                    "manual: la base contiene anclas no contempladas por el borrador: "
                    + ", ".join(sorted(missing))
                )
        same = (
            current["title"] == document["title"]
            and current["intro"] == document["intro"]
            and current["html"] == document["html"]
            and current["status"] == "proposal"
        )
        plan.append(("sin-cambios" if same else "versionar", document, current))
    return plan


def apply_plan(connection, plan):
    stamp = now()
    results = []
    for action, document, current in plan:
        slug = document["slug"]
        if action == "sin-cambios":
            results.append({"slug": slug, "accion": action, "version": current["version"]})
            continue
        if action == "crear":
            connection.execute(
                """INSERT INTO documents(slug,title,intro,version,status,html,updated,reference,hidden)
                   VALUES(?,?,?,1,'proposal',?,?,'',0)""",
                (slug, document["title"], document["intro"], document["html"], stamp),
            )
            connection.execute(
                """INSERT INTO revisions(document,version,html,status,reason,reference,author,created)
                   VALUES(?,1,?,'proposal',?,'',NULL,?)""",
                (slug, document["html"], REASON, stamp),
            )
            results.append({"slug": slug, "accion": action, "version": 1})
            continue
        version = current["version"] + 1
        connection.execute(
            """UPDATE documents SET title=?,intro=?,version=?,status='proposal',html=?,updated=?,reference=''
               WHERE slug=?""",
            (document["title"], document["intro"], version, document["html"], stamp, slug),
        )
        connection.execute(
            """INSERT INTO revisions(document,version,html,status,reason,reference,author,created)
               VALUES(?,?,?,'proposal',?,'',NULL,?)""",
            (slug, version, document["html"], REASON, stamp),
        )
        results.append({"slug": slug, "accion": action, "version": version})
    return results


def create_d07_thread(connection, author_username, comment_text):
    existing = connection.execute(
        "SELECT id FROM threads WHERE document='manual' AND title=? ORDER BY id LIMIT 1",
        (D07_TITLE,),
    ).fetchone()
    if existing:
        return {"accion": "sin-cambios", "thread_id": existing["id"]}
    if not isinstance(comment_text,str) or not comment_text.strip() or len(comment_text)>10000:
        raise ValueError("El comentario autorizado debe proporcionarse como texto privado de 1 a 10000 caracteres.")
    author = connection.execute(
        "SELECT * FROM users WHERE username=? AND active=1", (author_username,)
    ).fetchone()
    if author is None:
        raise RuntimeError(f"No existe una cuenta activa para {author_username}.")
    document = connection.execute(
        "SELECT * FROM documents WHERE slug='manual' AND hidden=0"
    ).fetchone()
    if document is None:
        raise RuntimeError("No existe el documento manual después de la importación.")
    part = next(
        (part for part in sections(document["html"]) if part["id"] == D07_SECTION), None
    )
    if part is None or D07_QUOTE not in part["text"]:
        raise RuntimeError("La sección o cita D07 no coincide con el manual importado.")
    stamp = now()
    cursor = connection.execute(
        """INSERT INTO threads(document,version,section,section_title,section_snapshot,quote,
                   prefix,suffix,title,topic,author,state,created,updated,target_type)
           VALUES('manual',?,?,?,?,?,'','',?,?,?,'open',?,?,'document')""",
        (
            document["version"],
            D07_SECTION,
            part["title"],
            part["text"],
            D07_QUOTE,
            D07_TITLE,
            short_sentence(comment_text),
            author["id"],
            stamp,
            stamp,
        ),
    )
    thread_id = cursor.lastrowid
    connection.execute(
        "INSERT INTO comments(thread_id,author,body,created) VALUES(?,?,?,?)",
        (thread_id, author["id"], comment_text.strip(), stamp),
    )
    event(
        connection,
        author["id"],
        "opened",
        "Luis Mario autorizó abrir esta discusión a partir de su respuesta de planeación D07.",
        thread_id,
    )
    return {"accion": "crear", "thread_id": thread_id}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, help="SQLite destino explícita.")
    parser.add_argument("--apply", action="store_true", help="Escribe dentro de una transacción.")
    parser.add_argument(
        "--backup-confirmed",
        action="store_true",
        help="Confirma que el operador preparó y verificó un respaldo antes de escribir.",
    )
    parser.add_argument(
        "--crear-hilo-d07",
        action="store_true",
        help="Crea idempotentemente el hilo autorizado de Luis Mario sobre redes.",
    )
    parser.add_argument("--autor-d07", default="luismario")
    parser.add_argument("--comentario-d07", type=Path, help="Archivo privado con el comentario autorizado; nunca se versiona.")
    parser.add_argument(
        "--imprimir-seed-d14",
        action="store_true",
        help="Imprime el JSON coordinado para la actividad del 15 de septiembre.",
    )
    args = parser.parse_args()

    if args.imprimir_seed_d14:
        print(json.dumps(ACTIVITY_SEED, ensure_ascii=False, indent=2))
        if not args.database and not args.apply:
            return
    documents = load_sources()
    print(f"HTML validados: {', '.join(document['slug'] for document in documents)}")

    if args.apply and not args.database:
        parser.error("--apply requiere --database explícita.")
    if args.apply and not args.backup_confirmed:
        parser.error("--apply requiere --backup-confirmed.")
    if args.crear_hilo_d07 and not args.apply:
        parser.error("--crear-hilo-d07 requiere --apply.")
    if args.crear_hilo_d07 and not args.comentario_d07:
        parser.error("--crear-hilo-d07 requiere --comentario-d07 con el texto autorizado fuera del repositorio.")
    if not args.database:
        print("Validación terminada. No se abrió una base ni se escribió contenido.")
        return
    if not args.database.is_file():
        parser.error("La base indicada no existe.")

    connection_context = (
        connect(args.database)
        if args.apply
        else sqlite3.connect(f"file:{args.database}?mode=ro", uri=True)
    )
    connection_context.row_factory = sqlite3.Row
    with connection_context as connection:
        if args.apply:
            connection.execute("BEGIN IMMEDIATE")
        plan = compare(connection, documents)
        print(json.dumps([
            {
                "slug": document["slug"],
                "accion": action,
                "version_actual": current["version"] if current else None,
            }
            for action, document, current in plan
        ], ensure_ascii=False, indent=2))
        if not args.apply:
            print("Vista previa terminada. Use --apply --backup-confirmed para escribir.")
            return
        results = apply_plan(connection, plan)
        thread = create_d07_thread(connection, args.autor_d07, args.comentario_d07.read_text(encoding='utf-8')) if args.crear_hilo_d07 else None
        connection.commit()
        print(json.dumps({"documentos": results, "hilo_d07": thread}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
