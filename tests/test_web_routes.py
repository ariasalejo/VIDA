"""Tests de integración de las rutas web de VIDA (Flask test client).

Pasan aislados: se parchea runtime_root, DATA y la raíz de cuentas a un
directorio temporal y se limpian las variables de entorno que cambian el
backend (Postgres, Vercel y clave de cifrado) para no tocar datos reales.

Ejecutar:  python3 -m pytest tests/ -q
"""
from __future__ import annotations

import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parent.parent

# Python >=3.14 no acepta valores None en os.environ: se usa cadena vacía.
NULL = {name: "" for name in ("POSTGRES_URL", "DATABASE_URL", "VERCEL", "NOW_REGION")}


class VIDAWebTestCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="vida_test_"))
        self.runtime = self.tmp / "runtime"
        self.runtime.mkdir()
        data_tmp = self.tmp / "data"
        (data_tmp / "courses").mkdir(parents=True)
        # Manifesto real del curso, copiado al almacén temporal de curso.
        manifest = ROOT / "data" / "course.json"
        if manifest.exists():
            (data_tmp / "courses" / "sena_ciberseguridad.json").write_text(
                manifest.read_text(encoding="utf-8"), encoding="utf-8"
            )
        # Token del certificado para el despliegue de prueba.
        (self.runtime / ".cert_token").write_text(
            "test-token-fija", encoding="utf-8"
        )

        from vida_engines import accounts as _accounts

        self.stack = (
            mock.patch.dict(os.environ, NULL, clear=False),
            mock.patch.object(__import__("vida"), "runtime_root", return_value=self.runtime),
            mock.patch.object(__import__("vida"), "DATA", data_tmp),
            mock.patch.object(__import__("vida"), "REGISTRY", data_tmp / "registry.json"),
            mock.patch.object(__import__("vida"), "COURSES_DIR", data_tmp / "courses"),
            mock.patch.object(__import__("vida"), "PROFILES_DIR", data_tmp / "profiles"),
            mock.patch.object(_accounts, "_root", return_value=self.tmp),
        )
        for patcher in self.stack:
            patcher.start()
        self.addCleanup(self._teardown)

        import vida

        self.app = vida.create_app()
        self.client = self.app.test_client()

    def _teardown(self):
        for patcher in self.stack:
            patcher.stop()
        if self.tmp.exists():
            import shutil
            shutil.rmtree(self.tmp, ignore_errors=True)

    # ---------- Navegación básica ----------

    def test_home_guest_returns_auth_screen(self):
        res = self.client.get("/")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Iniciar sesi", res.data)
        self.assertNotIn(b"EVIDENCIAS", res.data)

    def test_guest_momento_de_diario(self):
        res = self.client.get("/acceso/guest", follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"ENTREGA DE EVIDENCIAS", res.data)

    def test_certificate_route_requires_system_key(self):
        res = self.client.post("/api/certificate", json={})
        self.assertEqual(res.status_code, 403)

    # ---------- API pública ----------

    def test_api_course_serves_manifest(self):
        res = self.client.get("/api/course")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        items = {it["id"]: it for it in data.get("items", [])}
        self.assertIn("aa1", items)
        self.assertEqual(items["aa1"].get("kind"), "activity")
        guides = [m["file"] for m in items["aa1"].get("materials", [])]
        self.assertIn("media/materials/aa1_guia.html", guides)

    def test_api_activity_returns_item(self):
        res = self.client.get("/api/activity/aa2")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["id"], "aa2")

    def test_api_security_shape(self):
        res = self.client.get("/api/security")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertIn("evidence_encrypted", payload)
        self.assertIsInstance(payload["evidence_encrypted"], bool)

    def test_materials_guide_is_served(self):
        res = self.client.get("/media/materials/aa3_guia.html")
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"BLUMIX", res.data)
        self.assertIn(b"Matriz de riesgo", res.data)

    # ---------- Ciclo de cuenta + evidencia ----------

    def test_signup_login_and_evidence_upload(self):
        email = "prueba@vida.test"
        sign = self.client.post(
            "/api/auth/signup",
            json={"email": email, "name": "Prueba VIDA", "password": "secreto123"},
        )
        self.assertEqual(sign.status_code, 201)

        home = self.client.get("/")
        self.assertEqual(home.status_code, 200)
        self.assertIn(b"ENTREGA DE EVIDENCIAS", home.data)

        up = self.client.post(
            "/api/evidence/aa1",
            data={
                "file": (io.BytesIO(b"minuta de la evidencia aa1"), "minuta.pdf"),
                "note": "evidencia de prueba",
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(up.status_code, 201)
        body = up.get_json()
        self.assertTrue(body["ok"])
        self.assertTrue(body["url"].startswith("/media/evidence/aa1/"))

        download = self.client.get(body["url"])
        self.assertEqual(download.status_code, 200)
        self.assertEqual(download.data, b"minuta de la evidencia aa1")

        logout = self.client.post("/api/auth/logout")
        self.assertEqual(logout.status_code, 200)

    def test_evidence_upload_without_account_rejected(self):
        res = self.client.post(
            "/api/evidence/aa1",
            data={"file": (io.BytesIO(b"x"), "x.pdf")},
            content_type="multipart/form-data",
        )
        self.assertEqual(res.status_code, 401)

    # ---------- Garantías nuevas de VIDA ----------

    def test_security_headers_present(self):
        res = self.client.get("/api/course")
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.headers.get("X-Content-Type-Options"), "nosniff")
        self.assertEqual(res.headers.get("X-Frame-Options"), "DENY")
        self.assertIn("Content-Security-Policy", res.headers)
        self.assertIn("Referrer-Policy", res.headers)

    def test_api_security_integrity_shape(self):
        res = self.client.get("/api/security")
        self.assertEqual(res.status_code, 200)
        integrity = res.get_json()["integrity"]
        self.assertEqual(integrity["algorithm"], "SHA-256")
        self.assertTrue(integrity["tamper_evident"])
        self.assertIsInstance(integrity["evidence_count"], int)

    def test_evidence_overview_connects_activity_records(self):
        # Observación registrada SIN context.activity_id (caso de datos
        # existentes): el Centro de evidencias debe seguir mostrándola
        # relacionada con la actividad por su source.
        ev_dir = self.runtime / "evidence"
        ev_dir.mkdir(parents=True, exist_ok=True)
        (ev_dir / "evidence.json").write_text(
            json.dumps(
                [
                    {
                        "evidence_id": "EV-TEST00001",
                        "source": "work/aa1",
                        "method": "submission_confirmed",
                        "event_type": "ACTIVITY_COMPLETE",
                        "result": "DELIVERED",
                        "context": {"title": "AA1 · Informe de activos"},
                        "observed_at": "2026-09-12T00:00:00+00:00",
                        "status": "OBSERVED",
                    }
                ],
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        res = self.client.get("/api/evidence")
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertIn("total_records", payload)
        self.assertIn("groups", payload)
        aa1 = next(
            (g for g in payload["groups"] if g["activity_id"] == "aa1"),
            None,
        )
        self.assertIsNotNone(aa1)
        self.assertEqual(len(aa1["records"]), 1)
        self.assertEqual(aa1["records"][0]["source"], "work/aa1")
        self.assertEqual(payload["total_records"], 1)

    def test_certificate_css_is_landscape(self):
        css = (ROOT / "vida_ui_pro" / "style_cert.css").read_text(encoding="utf-8")
        self.assertIn("landscape", css)
        self.assertIn("@page", css)


class FernetCipherTestCase(unittest.TestCase):
    """Cifrado de datos en reposo: roundtrip y aislamiento de claves."""

    def test_roundtrip_with_env_key(self):
        with mock.patch.dict(os.environ, {"VIDA_DATA_KEY": "clave-maestra-de-prueba"}, clear=False):
            import importlib
            import vida_secret

            importlib.reload(vida_secret)
            payload = b"informe de activos que nunca debe filtrarse"
            token = vida_secret.encrypt(payload)
            self.assertIsNotNone(token)
            self.assertTrue(token.startswith(vida_secret.MAGIC))
            self.assertEqual(vida_secret.decrypt(token), payload)
            # Filas legacy sin la marca se devuelven exactamente igual.
            self.assertEqual(vida_secret.decrypt(payload), payload)
        import importlib as _il
        _il.reload(vida_secret)

    def test_different_key_rejected(self):
        with mock.patch.dict(os.environ, {"VIDA_DATA_KEY": "clave-a"}, clear=False):
            import importlib
            import vida_secret

            importlib.reload(vida_secret)
            token = vida_secret.encrypt(b"secreto")
        with mock.patch.dict(os.environ, {"VIDA_DATA_KEY": "clave-b"}, clear=False):
            importlib.reload(vida_secret)
            with self.assertRaises(ValueError):
                vida_secret.decrypt(token)
        importlib.reload(vida_secret)


if __name__ == "__main__":
    unittest.main()