"""Upload seguro de imagens de produto.

Regras (todas aplicadas no servidor):
- somente JPEG, PNG e WebP *reais* (o conteúdo é aberto e verificado com Pillow; extensão e MIME do navegador
  não são confiáveis e nunca decidem o formato salvo);
- limite de bytes por arquivo e limite de pixels (bloqueia decompression bombs) antes de decodificar;
- a imagem é reprocessada: orientação EXIF aplicada, metadados (EXIF, GPS, perfis, comentários) descartados,
  reduzida ao tamanho máximo e salva como JPEG (sem transparência) ou PNG (com transparência);
- o nome do arquivo é gerado no servidor (UUID). O nome enviado pelo navegador nunca vira caminho;
- a gravação é atômica (arquivo temporário + os.replace) dentro do diretório controlado;
- só é possível apagar arquivos que seguem o padrão gerado aqui (uploads/products/<uuid>.jpg|png).

Este módulo não depende do Flask: recebe os limites e o diretório como argumentos (fácil de testar).
"""
from __future__ import annotations

import io
import os
import re
import uuid
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP"}
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
ACCEPT_ATTR = "image/jpeg,image/png,image/webp"
UPLOAD_REL_DIR = "uploads/products"  # relativo a /static (é o que fica em Product.image)
# Único formato de nome que o painel gera e, portanto, o único que ele aceita apagar.
MANAGED_NAME_RE = re.compile(r"^uploads/products/[0-9a-f]{32}\.(jpg|png)$")


class UploadError(ValueError):
    """Erro de validação do upload, com mensagem segura para mostrar ao usuário."""


def _mib(n: int) -> str:
    value = n / (1024 * 1024)
    return f"{value:g} MiB"


def _read_limited(stream: BinaryIO, max_bytes: int) -> bytes:
    data = stream.read(max_bytes + 1)
    if not data:
        raise UploadError("O arquivo enviado está vazio. Escolha outra imagem.")
    if len(data) > max_bytes:
        raise UploadError(f"A imagem é grande demais. O tamanho máximo é {_mib(max_bytes)}.")
    return data


def process_image(data: bytes, *, max_pixels: int, max_side: int) -> tuple[bytes, str]:
    """Valida e reprocessa os bytes de uma imagem. Retorna (bytes_novos, extensão sem ponto)."""
    msg_invalid = "Arquivo inválido. Envie uma imagem JPG, PNG ou WebP."
    try:
        probe = Image.open(io.BytesIO(data))
        fmt = probe.format
        width, height = probe.size
    except (UnidentifiedImageError, OSError, ValueError, SyntaxError, Image.DecompressionBombError):
        raise UploadError(msg_invalid) from None
    if fmt not in ALLOWED_FORMATS:
        raise UploadError(msg_invalid)
    if width < 1 or height < 1:
        raise UploadError(msg_invalid)
    if width * height > max_pixels:
        raise UploadError("As dimensões da imagem são grandes demais. Reduza a imagem e tente novamente.")

    try:
        probe.verify()  # checa a estrutura sem decodificar tudo; invalida o objeto
        img = Image.open(io.BytesIO(data))
        img.load()  # decodifica de verdade (pega arquivos truncados/corrompidos)
        img = ImageOps.exif_transpose(img)
    except Exception:  # noqa: BLE001 — qualquer falha de decodificação vira erro amigável
        raise UploadError("Não foi possível ler essa imagem. Ela pode estar corrompida; tente outra.") from None

    has_alpha = img.mode in ("RGBA", "LA", "PA") or (img.mode == "P" and "transparency" in img.info)
    if has_alpha:
        img = img.convert("RGBA")
    elif img.mode != "RGB":
        img = img.convert("RGB")

    if max(img.size) > max_side:
        img.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)

    # Copia só os pixels para uma imagem nova: nada do arquivo original (metadados, perfis) sobrevive.
    clean = Image.new(img.mode, img.size)
    clean.paste(img)
    out = io.BytesIO()
    if has_alpha:
        clean.save(out, format="PNG", optimize=True)
        return out.getvalue(), "png"
    clean.save(out, format="JPEG", quality=85, optimize=True, progressive=True)
    return out.getvalue(), "jpg"


def validate_client_name(filename: str | None) -> None:
    """A extensão informada não decide o formato, mas extensões fora da lista são recusadas (ex.: .svg)."""
    ext = os.path.splitext(filename or "")[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise UploadError("Formato não permitido. Envie uma imagem JPG, PNG ou WebP.")


def save_product_image(stream: BinaryIO, filename: str | None, mimetype: str | None, *, upload_dir: Path,
                       max_bytes: int, max_pixels: int, max_side: int) -> str:
    """Valida, reprocessa e grava a imagem. Retorna o caminho relativo a /static (para Product.image)."""
    validate_client_name(filename)
    if (mimetype or "").lower().startswith("image/svg"):
        raise UploadError("Formato não permitido. Envie uma imagem JPG, PNG ou WebP.")
    data = _read_limited(stream, max_bytes)
    new_bytes, ext = process_image(data, max_pixels=max_pixels, max_side=max_side)

    upload_dir = Path(upload_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}.{ext}"
    final_path = (upload_dir / name).resolve()
    if final_path.parent != upload_dir.resolve():  # defesa extra contra path traversal
        raise UploadError("Não foi possível salvar a imagem.")
    tmp_path = upload_dir / f".tmp-{uuid.uuid4().hex}"
    try:
        with open(tmp_path, "wb") as fh:
            fh.write(new_bytes)
        os.replace(tmp_path, final_path)
    except OSError:
        _silent_unlink(tmp_path)
        raise UploadError("Não foi possível salvar a imagem no servidor. Tente novamente.") from None
    return f"{UPLOAD_REL_DIR}/{name}"


def is_managed_image(rel_path: str | None) -> bool:
    return bool(rel_path and MANAGED_NAME_RE.match(rel_path))


def delete_managed_image(rel_path: str | None, *, upload_dir: Path) -> bool:
    """Apaga somente arquivos gerados pelo painel (padrão uploads/products/<uuid>.ext). Nunca toca nos SVGs
    originais do projeto nem em nada fora do diretório de uploads."""
    if not is_managed_image(rel_path):
        return False
    upload_dir = Path(upload_dir).resolve()
    target = (upload_dir / rel_path.rsplit("/", 1)[1]).resolve()
    if target.parent != upload_dir or not target.is_file():
        return False
    return _silent_unlink(target)


def _silent_unlink(path: Path) -> bool:
    try:
        Path(path).unlink()
        return True
    except OSError:
        return False
