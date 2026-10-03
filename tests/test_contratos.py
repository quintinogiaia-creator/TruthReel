import pytest
from pydantic import ValidationError

from mybestia_video.contratos import Dossier, Guion, Tema


def test_guion_exige_tres_secciones_sin_parrafos_vacios():
    ok = {"secciones": [{"id": f"s{i}", "parrafos": ["hola"]} for i in range(3)], "fonetica": []}
    assert Guion.model_validate(ok).palabras() == 3
    with pytest.raises(ValidationError):
        Guion.model_validate({"secciones": ok["secciones"][:2]})
    malo = {"secciones": ok["secciones"][:2] + [{"id": "s3", "parrafos": ["  "]}]}
    with pytest.raises(ValidationError):
        Guion.model_validate(malo)


def test_dossier_vacio_no_vale():
    with pytest.raises(ValidationError):
        Dossier(texto="")


def test_tema_rechaza_campos_desconocidos():
    with pytest.raises(ValidationError):
        Tema(tema="un tema largo", pid="x", sobra=1)


def test_kit_sin_imagenes_ia_no_vale():
    from mybestia_video.contratos import Kit
    with pytest.raises(ValidationError):
        Kit(carpeta="k", imagenes_ia=["img_ia_0"])
