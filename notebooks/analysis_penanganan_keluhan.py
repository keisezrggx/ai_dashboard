from pathlib import Path
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "dataset_wellbore"

DATA_FILES = [
    DATA_DIR / "akulaku_superset_presto_hanmm_ozy.prazuganda_1792482311_09_01_05.csv",
    DATA_DIR / "akulaku_superset_presto_hanmm_ozy.prazuganda_1792482495_09_06_10.csv",
    DATA_DIR / "akulaku_superset_presto_hanmm_ozy.prazuganda_1792482595_09_11_15.csv",
    DATA_DIR / "akulaku_superset_presto_hanmm_ozy.prazuganda_1792482774_09_16_20.csv",
    DATA_DIR / "akulaku_superset_presto_hanmm_ozy.prazuganda_1792482909_09_21_25.csv",
    DATA_DIR / "akulaku_superset_presto_hanmm_ozy.prazuganda_1792483754_09_26_30.csv",
]

def load_multiple_csv(file_paths: list[Path]) -> pd.DataFrame:
    frames = []

    for file_path in file_paths:
        if not file_path.is_file():
            raise FileNotFoundError(f"CSV file not found: {file_path}")

        frames.append(pd.read_csv(file_path))

    if not frames:
        raise ValueError("no CSV files provided.")

    return pd.concat(frames, ignore_index=True)

def call_llm_analysis(dataset_summary: dict[str, object], analysis_prompt: str) -> str:
    base_url = os.environ.get("LLM_BASE_URL", "").strip().rstrip("/")
    model = os.environ.get("LLM_MODEL", "").strip()
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()

    if not base_url or not model or not api_key:
        raise EnvironmentError(
            "Set LLM_BASE_URL, LLM_MODEL, and OPENAI_API_KEY before calling the LLM."
        )

    endpoint = f"{base_url}/chat/completions"
    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "Analyze only supplied aggregate data. Do not invent metrics or "
                    "claim that aggregate data verifies conversation-level findings. "
                    "State which claims cannot be checked from the supplied fields."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"{analysis_prompt}\n\n"
                    "September dataset summary (JSON):\n"
                    f"{json.dumps(dataset_summary, ensure_ascii=False, default=str)}"
                ),
            },
        ],
        "temperature": 0.1,
    }
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + api_key,
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urlopen(request, timeout=120) as response:
            result = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        details = error.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"LLM API returned HTTP {error.code}: {details}") from error
    except URLError as error:
        raise RuntimeError(f"Could not reach LLM API: {error.reason}") from error

    try:
        return result["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as error:
        raise ValueError("LLM API response did not contain chat completion content.") from error


def main() -> None:
    df = load_multiple_csv(DATA_FILES)

    if "transfermanualtime" not in df.columns:
        raise KeyError("Required column missing: transfermanualtime")

    df["transferred_to_agent"] = df["transfermanualtime"].notna()

    print(f"Rows loaded: {len(df):,}")
    print(f"Transferred to agent: {df['transferred_to_agent'].sum():,}")
    print(f"Kula ended conversations: {(~df['transferred_to_agent']).sum():,}")
    print(f"Transfer rate: {df['transferred_to_agent'].mean():.1%}")

    if "--analyze" not in sys.argv:
        print("LLM analysis skipped. Pass --analyze to send aggregates to configured API.")
        return

    summary_fields = [
        "Category 1", "Category 2", "Category 3", "summary_type",
        "summary_classify", "question_category1", "question_category2",
        "closesource", "labels", "solved_num", "unsolved_num",
        "transferred_to_agent",
    ]
    available_fields = [field for field in summary_fields if field in df.columns]
    summary = {
        "total_conversations": int(len(df)),
        "transfer_count": int(df["transferred_to_agent"].sum()),
        "transfer_rate": float(df["transferred_to_agent"].mean()),
        "categorical_counts": {},
    }
    for field in available_fields:
        counts = df[field].fillna("(missing)").astype(str).value_counts().head(100)
        summary["categorical_counts"][field] = {
            str(label): int(count) for label, count in counts.items()
        }

    result = call_llm_analysis(summary, prompt)
    print("\n=== LLM analysis ===\n")
    print(result)


prompt = '''
There is previous analysis on kula dataset. here are the findings briefly summarized:

Masalah yang terlihat dari proses penanganan.
- Masalah yang sudah dijelaskan terkonsentrasi pada pinjaman dan pembayaran.
Setelah mengeluarkan percakapan yang hanya menyapa atau tidak menjelaskan masalah, tiga kategori tertinggi adalah pengajuan pinjaman ditolak atau gagal (41,227 percakapan, 11.6%), limit atau Paylater tidak bisa dipakai (35,048 percakapan, 9.9%), dan tidak bisa menyelesaikan pembayaran (25,058 percakapan, 7.0%). Berikutnya adalah pengiriman logistik (18,659 percakapan) dan sudah bayar tetapi tagihan masih ada (16,049 percakapan). Ada pula 43,443 percakapan (12.2%) yang hanya menyapa atau hanya mengetuk nama produk, sehingga AI belum mulai menangani masalah.

- AI sering langsung menyerahkan masalah yang sudah jelas ke agen
240,005 percakapan berisi ucapan AI. Di antaranya, tindakan utama pada 76,420 percakapan adalah mengarahkan ke agen; 38,615 percakapan dialihkan tanpa jawaban yang sesuai masalah, yaitu 16.1% dari percakapan yang ada AI. Yang diberi langkah-langkah ada 77,119 percakapan. Pengguna yang kemudian secara jelas mengatakan puas ada 18,204 percakapan, yang secara jelas tidak puas ada 6,114 percakapan. Sisa 215,687 percakapan ada AI, tetapi pengguna tidak menyatakan sikap. Di antara 24,318 percakapan yang sikapnya jelas, yang puas 74.9%. Penutupan akun adalah salah satu dari sedikit masalah yang ditangani AI sendiri: dari 10,918 percakapan, 7,462 diberi langkah-langkah, dan yang dialihkan ke agen hanya 22%.

- Setengah percakapan agen berhenti karena pengguna tidak berbicara lagi
Agen muncul di 163,766 percakapan. Rata-rata waktu balasan agen adalah 30 detik; yang terlama 38 jam 9 menit. Jika balasan lebih dari 10 menit, dalam 71.6% kasus pengguna tidak berbicara lagi. 89,889 percakapan (54.9%) diakhiri agen setelah pengguna tidak membalas lagi, tanpa kesimpulan penanganan dalam percakapan. 64,611 percakapan (39.5%) sebagian besar berhenti pada permintaan tangkapan layar, konfirmasi produk, atau verifikasi identitas. Setelah agen memeriksa lalu memberi kesimpulan pencarian ada 2,622 percakapan. Yang secara jelas mengatakan puas ada 27,051 percakapan, yang secara jelas tidak puas ada 8,631 percakapan. Di percakapan yang sikapnya jelas, yang puas 75.8%. Pada kategori penyalahgunaan, penipuan, atau tagihan bukan milik sendiri, dari 1,275 percakapan, ketidakpuasan setelah penanganan agen adalah hasil dengan proporsi tertinggi (548 percakapan, 43%), dan proporsi alih ke agen 77%.

- Beberapa jenis masalah punya proporsi alih ke agen yang sangat tinggi
Percakapan yang hanya minta dialihkan ke agen, 90% sampai ke agen. Penyalahgunaan atau tagihan bukan milik sendiri 77%, perubahan data 76%, penagihan datang ke rumah atau pelecehan 75%, surat keterangan lunas 68%, pembayaran berhasil tetapi tagihan belum lunas 63%. Pada kategori pembayaran yang belum tercatat lunas, tindakan AI yang paling umum tetap penjelasan umum, tanpa tindakan pencatatan pelunasan yang jelas, dan sebagian besar jatuh ke agen. Di sisi agen, hasil yang paling umum tetap percakapan berakhir setelah pengguna tidak membalas lagi.

I want you to check and verify those findings with my current real dataset of september that I gathered and stored into DF. here are the information that you need to know to proceed this analysis: 
- the parameter that show is the user transfered into agent live or not is the column transfermanualtime. if there's data in that columns, that mean user have transfered into human agent.

'''


if __name__ == "__main__":
    main()