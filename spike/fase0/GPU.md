# GPU (Tarea 7) — RTX 3060 Laptop 6 GB, driver 615.78

Funciona. Venv aparte porque `onnxruntime-gpu` no convive con `onnxruntime`:

```bash
/usr/bin/python3 -m venv spike/fase0/.venv-gpu
spike/fase0/.venv-gpu/bin/python -m pip install "onnxruntime-gpu[cuda,cudnn]" "psycopg[binary]" pyyaml numpy "huggingface-hub<2.0,>=0.20"
spike/fase0/.venv-gpu/bin/python -m pip install --no-deps fastembed   # + sus dependencias menos onnxruntime
```

- Las librerías CUDA/cuDNN llegan como wheels de NVIDIA; `onnxruntime.preload_dlls()` las carga
  (lo hace `comun._providers`). No hace falta instalar el CUDA Toolkit del sistema.
- `fastembed 0.9.1` exige `huggingface-hub<2.0`; pip instala 2.x por defecto y hay que fijarlo.
- **Los modelos int8 no aceleran en CUDA**: `bge-reranker-v2-m3-int8` da 8,6 pares/s en GPU (≈ CPU) porque
  sus operadores cuantizados caen a CPU. En GPU se usa la versión fp32 `BAAI/bge-reranker-v2-m3`: 61,7 pares/s
  con la misma calidad (0,95).

| Modelo | CPU | GPU | × |
|---|---|---|---|
| jina-reranker-v2-base-multilingual (pares/s) | 10,0 | 178,6 | 18 |
| bge-reranker-v2-m3 fp32 (pares/s) | — | 61,7 | — |
| paraphrase-multilingual-MiniLM-L12-v2 (unidades/s) | 394 | 8.370 | 21 |
| multilingual-e5-small (unidades/s) | 403 | 3.643 | 9 |
| potion-multilingual-128M (unidades/s) | 67.381 | 64.976 | 1 (modelo estático, no usa la GPU) |
