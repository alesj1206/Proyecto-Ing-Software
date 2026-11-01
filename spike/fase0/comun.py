from pathlib import Path

import psycopg

ENV_POSTGRES = Path(__file__).resolve().parents[2] / "infra" / "postgres" / ".env"
RESULTADOS = Path(__file__).resolve().parent / "resultados"


def _leer_env(ruta: Path) -> dict[str, str]:
    pares = (linea.split("=", 1) for linea in ruta.read_text().splitlines() if "=" in linea and not linea.startswith("#"))
    return {k.strip(): v.strip() for k, v in pares}


def conectar() -> psycopg.Connection:
    env = _leer_env(ENV_POSTGRES)
    return psycopg.connect(
        host="localhost",
        port=env["POSTGRES_PORT"],
        user=env["POSTGRES_USER"],
        password=env["POSTGRES_PASSWORD"],
        dbname=env["POSTGRES_DB"],
        autocommit=True,
    )


CACHE_MODELOS = Path.home() / ".cache" / "scoutly-modelos"

# e5 no viene de fábrica en fastembed 0.9: se registra desde el ONNX oficial de Hugging Face.
E5_PERSONALIZADOS = {"intfloat/multilingual-e5-small": 384, "intfloat/multilingual-e5-base": 768}

MODELOS_EMBEDDING = [
    "intfloat/multilingual-e5-small",
    "intfloat/multilingual-e5-base",
    "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2",
    "sentence-transformers/paraphrase-multilingual-mpnet-base-v2",
    "minishlab/potion-multilingual-128M",
]
MODELOS_RERANKER = [
    "BAAI/bge-reranker-v2-m3-int8",
    "BAAI/bge-reranker-v2-m3",  # fp32: solo tiene sentido en GPU (en CPU es más lento que el int8)
    "jinaai/jina-reranker-v2-base-multilingual",
]


def usa_prefijo_e5(modelo: str) -> bool:
    return modelo.startswith("intfloat/")


def _registrar_e5() -> None:
    from fastembed import TextEmbedding
    from fastembed.common.model_description import ModelSource, PoolingType

    ya = {m["model"] for m in TextEmbedding.list_supported_models()}
    for nombre, dim in E5_PERSONALIZADOS.items():
        if nombre not in ya:
            TextEmbedding.add_custom_model(
                model=nombre, pooling=PoolingType.MEAN, normalization=True,
                sources=ModelSource(hf=nombre), dim=dim, model_file="onnx/model.onnx",
            )


def _providers(proveedor: str) -> list[str]:
    if proveedor != "cuda":
        return ["CPUExecutionProvider"]
    import onnxruntime

    # Las librerías CUDA/cuDNN vienen como wheels de nvidia: hay que precargarlas antes de crear la sesión.
    getattr(onnxruntime, "preload_dlls", lambda: None)()
    # Sin esto, onnxruntime cae a CPU en silencio y el benchmark reportaría CPU como si fuera GPU.
    if "CUDAExecutionProvider" not in onnxruntime.get_available_providers():
        raise RuntimeError("CUDAExecutionProvider no disponible en este onnxruntime")
    return ["CUDAExecutionProvider"]


def cargar_embedding(modelo: str, proveedor: str = "cpu"):
    from fastembed import TextEmbedding

    _registrar_e5()
    return TextEmbedding(modelo, cache_dir=str(CACHE_MODELOS), providers=_providers(proveedor))


def cargar_reranker(modelo: str, proveedor: str = "cpu"):
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    return TextCrossEncoder(modelo, cache_dir=str(CACHE_MODELOS), providers=_providers(proveedor))
