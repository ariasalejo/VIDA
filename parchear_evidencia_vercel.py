#!/usr/bin/env python3
"""Parchea VIDA para persistir evidencias en Vercel Blob.

No despliega nada.
Crea backup antes de modificar vida.py.
"""

from __future__ import annotations

import re
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
VIDA = ROOT / "vida.py"
REQ = ROOT / "requirements.txt"
BACKUP = ROOT / "vida.py.backup-before-vercel-blob"
MARKER = "# === VIDA VERCEL BLOB EVIDENCE PATCH ==="


HELPERS = r'''
    # === VIDA VERCEL BLOB EVIDENCE PATCH ===
    def _vercel_blob_enabled() -> bool:
        """Activa Blob cuando Vercel proporciona su token."""
        return bool(os.getenv("BLOB_READ_WRITE_TOKEN"))


    def _vercel_blob_client():
        """Carga el SDK solo cuando Blob está habilitado."""
        from vercel.blob import BlobClient
        return BlobClient()


    def _vercel_blob_prefix(activity_id: str) -> str:
        """Aísla evidencias por usuario, curso y actividad."""
        uid = str(current_user_id())
        cid = str(active_course_id())
        return f"vida/evidence/{uid}/{cid}/{activity_id}/"


    def _vercel_blob_read(pathname: str) -> bytes:
        client = _vercel_blob_client()
        result = client.get(pathname, access="private")

        if (
            result is None
            or result.status_code != 200
            or result.stream is None
        ):
            raise FileNotFoundError(pathname)

        return b"".join(result.stream)


    def _vercel_blob_list(activity_id: str) -> list:
        client = _vercel_blob_client()
        prefix = _vercel_blob_prefix(activity_id)

        blobs = []
        cursor = None

        while True:
            page = client.list_objects(
                prefix=prefix,
                limit=1000,
                cursor=cursor,
            )

            blobs.extend(page.blobs)

            if not page.has_more:
                break

            cursor = page.cursor

        return blobs


    def _vercel_blob_records(activity_id: str) -> list[dict]:
        records = []

        for blob in _vercel_blob_list(activity_id):
            pathname = blob.pathname

            if not pathname.endswith(".json"):
                continue

            try:
                payload = json.loads(
                    _vercel_blob_read(pathname).decode("utf-8")
                )
            except (
                OSError,
                ValueError,
                UnicodeDecodeError,
            ):
                continue

            if isinstance(payload, dict):
                records.append(payload)

        records.sort(
            key=lambda item: item.get("observed_at", "")
        )

        return records


    def _vercel_blob_files(activity_id: str) -> list[dict]:
        files = []

        for blob in _vercel_blob_list(activity_id):
            pathname = blob.pathname

            if pathname.endswith(".json"):
                continue

            name = pathname.rsplit("/", 1)[-1]

            files.append(
                {
                    "name": name,
                    "size": int(blob.size or 0),
                    "url": (
                        f"/media/evidence/"
                        f"{activity_id}/{name}"
                    ),
                }
            )

        files.sort(
            key=lambda item: item["name"]
        )

        return files


    def _vercel_blob_store_evidence(
        activity_id: str,
        stored_name: str,
        body: bytes,
        content_type: str | None,
        record: dict,
    ) -> None:
        client = _vercel_blob_client()
        prefix = _vercel_blob_prefix(activity_id)

        client.put(
            prefix + stored_name,
            body,
            access="private",
            content_type=(
                content_type
                or "application/octet-stream"
            ),
            add_random_suffix=False,
        )

        client.put(
            prefix + str(record["evidence_id"]) + ".json",
            json.dumps(
                record,
                indent=2,
                ensure_ascii=False,
            ).encode("utf-8"),
            access="private",
            content_type="application/json",
            add_random_suffix=False,
        )

    # === FIN VIDA VERCEL BLOB EVIDENCE PATCH ===
'''


EVIDENCE_OVERVIEW = r'''    @app.get("/api/evidence")
    def evidence_overview():
        course_data = course()
        result = []

        for item in course_data.get("items", []):
            if item.get("kind") != "activity":
                continue

            activity_id = item["id"]

            if _vercel_blob_enabled():
                records = _vercel_blob_records(activity_id)
                files = _vercel_blob_files(activity_id)
            else:
                records = _evidence_for(activity_id)
                files = _uploaded_files(activity_id)

            result.append(
                {
                    "activity_id": activity_id,
                    "title": item.get(
                        "title",
                        activity_id,
                    ),
                    "records": records,
                    "files": files,
                }
            )

        return jsonify(result)
'''


UPLOAD_EVIDENCE = r'''    @app.post("/api/evidence/<activity_id>")
    def upload_evidence(activity_id: str):
        from werkzeug.utils import secure_filename

        if "file" not in request.files:
            return jsonify(
                {
                    "ok": False,
                    "error": "No se recibió archivo.",
                }
            ), 400

        upload = request.files["file"]

        if not upload or not upload.filename:
            return jsonify(
                {
                    "ok": False,
                    "error": "Archivo vacío.",
                }
            ), 400

        safe = secure_filename(
            upload.filename
        ).lower()

        allowed = {
            "pdf",
            "png",
            "jpg",
            "jpeg",
            "gif",
            "webp",
            "xlsx",
            "xls",
            "doc",
            "docx",
            "ppt",
            "pptx",
            "txt",
            "zip",
        }

        if (
            "." not in safe
            or safe.rsplit(".", 1)[1] not in allowed
        ):
            return jsonify(
                {
                    "ok": False,
                    "error": "Formato no permitido.",
                }
            ), 400

        stamp = datetime.now(
            timezone.utc
        ).strftime(
            "%Y%m%d_%H%M%S_%f"
        )

        stored_name = (
            f"{stamp}_{safe}"
        )

        if _vercel_blob_enabled():
            try:
                body = upload.read()

                if not body:
                    return jsonify(
                        {
                            "ok": False,
                            "error": "Archivo vacío.",
                        }
                    ), 400

                from vida_engines import EvidenceEngine

                evidence = EvidenceEngine(
                    evidence_root()
                    / "evidence.json"
                )

                record = evidence.record(
                    source=(
                        f"work/{activity_id}"
                    ),
                    method="evidence_upload",
                    event_type=(
                        "ACTIVITY_COMPLETE"
                    ),
                    result="DELIVERED",
                    context={
                        "activity_id": activity_id,
                        "user_id": (
                            current_user_id()
                        ),
                        "course_id": (
                            active_course_id()
                        ),
                        "file": stored_name,
                        "size": len(body),
                        "note": str(
                            request.form.get(
                                "note",
                                "",
                            )
                        ),
                    },
                )

                _vercel_blob_store_evidence(
                    activity_id=activity_id,
                    stored_name=stored_name,
                    body=body,
                    content_type=upload.mimetype,
                    record=record.to_dict(),
                )

            except Exception as exc:
                app.logger.exception(
                    "Error guardando evidencia "
                    "en Vercel Blob"
                )

                return jsonify(
                    {
                        "ok": False,
                        "error": (
                            "No se pudo guardar "
                            "la evidencia en Blob: "
                            f"{exc}"
                        ),
                    }
                ), 503

            try:
                connection = conn()
                cid = active_course_id()
                uid = current_user_id()

                connection.execute(
                    """
                    INSERT INTO item_progress
                        (
                            user_id,
                            item_id,
                            course_id,
                            completed
                        )
                    VALUES (?, ?, ?, 1)
                    ON CONFLICT(
                        user_id,
                        item_id,
                        course_id
                    )
                    DO UPDATE SET
                        completed = 1,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (
                        uid,
                        activity_id,
                        cid,
                    ),
                )

                connection.commit()
                connection.close()

            except Exception:
                app.logger.exception(
                    "No se pudo actualizar "
                    "item_progress"
                )

            return jsonify(
                {
                    "ok": True,
                    "evidence_id": (
                        record.evidence_id
                    ),
                    "file": stored_name,
                    "url": (
                        f"/media/evidence/"
                        f"{activity_id}/"
                        f"{stored_name}"
                    ),
                    "storage": "vercel_blob",
                }
            ), 201

        # ============================
        # MODO LOCAL
        # ============================

        evidence_dir = (
            evidence_root()
            / activity_id
        )

        try:
            evidence_dir.mkdir(
                parents=True,
                exist_ok=True,
            )

        except OSError:
            return jsonify(
                {
                    "ok": False,
                    "error": (
                        "No se pudo escribir "
                        "en el almacén de "
                        "evidencias de este "
                        "despliegue."
                    ),
                }
            ), 503

        path = (
            evidence_dir
            / stored_name
        )

        try:
            upload.save(path)

        except OSError:
            return jsonify(
                {
                    "ok": False,
                    "error": (
                        "No se pudo guardar "
                        "la evidencia en este "
                        "despliegue."
                    ),
                }
            ), 503

        from vida_engines import EvidenceEngine

        evidence = EvidenceEngine(
            evidence_root()
            / "evidence.json"
        )

        record = evidence.record(
            source=(
                f"work/{activity_id}"
            ),
            method="evidence_upload",
            event_type=(
                "ACTIVITY_COMPLETE"
            ),
            result="DELIVERED",
            context={
                "activity_id": activity_id,
                "user_id": (
                    current_user_id()
                ),
                "course_id": (
                    active_course_id()
                ),
                "file": stored_name,
                "size": path.stat().st_size,
                "note": str(
                    request.form.get(
                        "note",
                        "",
                    )
                ),
            },
        )

        connection = conn()
        cid = active_course_id()
        uid = current_user_id()

        connection.execute(
            """
            INSERT INTO item_progress
                (
                    user_id,
                    item_id,
                    course_id,
                    completed
                )
            VALUES (?, ?, ?, 1)
            ON CONFLICT(
                user_id,
                item_id,
                course_id
            )
            DO UPDATE SET
                completed = 1,
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                uid,
                activity_id,
                cid,
            ),
        )

        connection.commit()
        connection.close()

        return jsonify(
            {
                "ok": True,
                "evidence_id": (
                    record.evidence_id
                ),
                "file": stored_name,
                "url": (
                    f"/media/evidence/"
                    f"{activity_id}/"
                    f"{stored_name}"
                ),
                "storage": "filesystem",
            }
        ), 201
'''


MEDIA_EVIDENCE = r'''    @app.get("/media/evidence/<activity_id>/<path:name>")
    def media_evidence(
        activity_id: str,
        name: str,
    ):
        if _vercel_blob_enabled():
            pathname = (
                _vercel_blob_prefix(
                    activity_id
                )
                + name
            )

            try:
                result = (
                    _vercel_blob_client()
                    .get(
                        pathname,
                        access="private",
                    )
                )

            except Exception:
                app.logger.exception(
                    "Error leyendo evidencia "
                    "desde Vercel Blob"
                )

                return jsonify(
                    {
                        "ok": False,
                        "error": (
                            "No se pudo leer "
                            "la evidencia."
                        ),
                    }
                ), 503

            if (
                result is None
                or result.status_code != 200
                or result.stream is None
            ):
                return jsonify(
                    {
                        "ok": False,
                        "error": (
                            "Evidencia no encontrada."
                        ),
                    }
                ), 404

            headers = {
                "Cache-Control": (
                    "private, no-store"
                )
            }

            if result.blob.content_type:
                headers["Content-Type"] = (
                    result.blob.content_type
                )

            return Response(
                result.stream,
                headers=headers,
            )

        return send_from_directory(
            evidence_root()
            / activity_id,
            name,
            as_attachment=False,
        )
'''


def replace_nested_function(
    text: str,
    decorator: str,
    function_name: str,
    replacement: str,
) -> str:
    """Reemplaza una función anidada dentro de create_app()."""

    pattern = re.compile(
        rf"(?ms)^    {re.escape(decorator)}\n"
        rf"    def {re.escape(function_name)}\(.*?"
        rf"(?=^    @app\.|\n^    return app\b)",
    )

    match = pattern.search(text)

    if not match:
        raise RuntimeError(
            f"No encontré la función "
            f"{function_name}() con indentación esperada."
        )

    return (
        text[:match.start()]
        + replacement.rstrip()
        + "\n\n"
        + text[match.end():]
    )


def main() -> None:
    if not VIDA.exists():
        raise SystemExit(
            f"❌ No existe: {VIDA}"
        )

    original = VIDA.read_text(
        encoding="utf-8"
    )

    if MARKER in original:
        raise SystemExit(
            "⚠️ El parche ya aparece instalado "
            "en vida.py. No duplico cambios."
        )

    required = [
        '    @app.get("/api/evidence")',
        "    def evidence_overview():",
        '    @app.post("/api/evidence/<activity_id>")',
        "    def upload_evidence(activity_id: str):",
        '    @app.get("/media/evidence/<activity_id>/<path:name>")',
        "    def media_evidence(activity_id: str, name: str):",
    ]

    missing = [
        item
        for item in required
        if item not in original
    ]

    if missing:
        raise SystemExit(
            "❌ No encontré en vida.py:\n"
            + "\n".join(
                f"   - {item}"
                for item in missing
            )
        )

    # Backup solamente antes de escribir.
    shutil.copy2(
        VIDA,
        BACKUP,
    )

    # Inserta helpers antes de /api/evidence.
    anchor = original.find(
        '    @app.get("/api/evidence")'
    )

    if anchor < 0:
        raise SystemExit(
            "❌ No encontré el endpoint "
            "/api/evidence"
        )

    text = (
        original[:anchor]
        + HELPERS
        + "\n"
        + original[anchor:]
    )

    text = replace_nested_function(
        text,
        '@app.get("/api/evidence")',
        "evidence_overview",
        EVIDENCE_OVERVIEW,
    )

    text = replace_nested_function(
        text,
        '@app.post("/api/evidence/<activity_id>")',
        "upload_evidence",
        UPLOAD_EVIDENCE,
    )

    text = replace_nested_function(
        text,
        '@app.get("/media/evidence/<activity_id>/<path:name>")',
        "media_evidence",
        MEDIA_EVIDENCE,
    )

    VIDA.write_text(
        text,
        encoding="utf-8",
    )

    # Añadir SDK Vercel.
    if REQ.exists():
        req = REQ.read_text(
            encoding="utf-8"
        )

        if not re.search(
            r"(?im)^vercel\s*[<=>~]",
            req,
        ):
            if req and not req.endswith("\n"):
                req += "\n"

            req += (
                "vercel>=0.10,<1\n"
            )

            REQ.write_text(
                req,
                encoding="utf-8",
            )

    else:
        REQ.write_text(
            "vercel>=0.10,<1\n",
            encoding="utf-8",
        )

    print("🔥 PARCHE INSTALADO")
    print(
        f"   Backup: {BACKUP.name}"
    )
    print("   vida.py: OK")
    print(
        "   requirements.txt: "
        "SDK Vercel añadido"
    )
    print()
    print("Verificaciones:")
    print(
        "  python -m py_compile vida.py"
    )
    print(
        "  python -m unittest discover "
        "-s tests -p 'test_*.py'"
    )
    print()
    print(
        "NO hagas deploy de Production todavía."
    )


if __name__ == "__main__":
    main()
