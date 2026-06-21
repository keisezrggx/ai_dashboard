"""
Indonesian Typo Correction Script for AI Voice Data
=====================================================
This script fixes typos in Indonesian language text from the '原始语音' (original speech) column 
and writes the corrected text to the 'Kalimat (fixed)' column.

Total corrections: 129 rows

Usage:
  - Run this script directly: python fix_typos.py
  - Or import and use in your notebook:
      from fix_typos import apply_typo_corrections
      df_clean = apply_typo_corrections(df_clean)
"""

import pandas as pd

# ============================================================
# TYPO CORRECTIONS DICTIONARY
# Key = row number (序号), Value = corrected Indonesian text
# Only rows with actual typos are included
# ============================================================

typo_corrections = {
    # Row 2: "q8" -> "28" (speech recognition error for number)
    2: "saya bayar nya tgl 28",
    
    # Row 4: "melakukan melakukan" -> duplicate word removed
    4: "kenapa saya tidak bisa melakukan pinjaman dana?",
    
    # Row 9: "di pakai" -> "dipakai" (di-prefix spacing)
    9: "kenapa limit Paylater tidak bisa dipakai",
    
    # Row 19: "gimna" -> "gimana"
    19: "gimana biar bisa bayar beberapa transaksi sekaligus",
    
    # Row 21: "knp tdak bsa pkai" -> "kenapa tidak bisa pakai"
    21: "kenapa tidak bisa pakai limit paylater",
    
    # Row 30: "nasi kado" -> "kasih kado" (speech recognition error)
    30: "kasih kado buat istri saya.",
    
    # Row 32: "c bank" -> "seabank"
    32: "halo alika, saya sudah melakukan pembayaran melalui seabank ke tagihan hari ini, kenapa belum masuk ya?",
    
    # Row 33: "munggunakan" -> "menggunakan", "pay leter" -> "paylater"
    33: "kenapa saya tidak bisa menggunakan paylater saya",
    
    # Row 37: "di tolak" -> "ditolak"
    37: "kenapa pinjaman ditolak",
    
    # Row 42: "pulsnya" -> "pulsanya"
    42: "aku pinjam pulsanya 150",
    
    # Row 47: "knpa sya" -> "kenapa saya"
    47: "kenapa saya tidak bisa menggunakan paylater pulsa",
    
    # Row 49: "knapa" -> "kenapa"
    49: "kenapa paylater saya nggak bisa digunakan",
    
    # Row 51: "byr" -> "bayar", "tp" -> "tapi"
    51: "mau bayar lewat DANA tapi ga ada opsinya",
    
    # Row 52: "pay letter" -> "paylater"
    52: "paylater dan pinjaman ini nggak bisa dipakai ini kak gimana ya? soalnya udah lunas di tahun kemarin.",
    
    # Row 59: "bs bi bantu" -> "bisa dibantu"
    59: "saya mau bayar lewat alfamart. bisa dibantu",
    
    # Row 81: "file letter" -> "paylater" (speech recognition error)
    81: "kenapa paylater saya tidak bisa digunakan?",
    
    # Row 82: "file explorer" -> "paylater" (speech recognition error)
    82: "kenapa paylater saya tidak bisa digunakan?",
    
    # Row 87: "hrs krm atw gmn" -> "harus kirim atau gimana"
    87: "mau angsuran pinjaman, bukti pembayarannya harus kirim atau gimana",
    
    # Row 88: "sy" -> "saya", "di krm atw gmn ea" -> "dikirim atau gimana ya"
    88: "saya mau angsuran pinjaman, bukti pembayarannya dikirim atau gimana ya",
    
    # Row 91: "aku laku" -> "akulaku"
    91: "cara mengetahui limit offline saya di spaylater akulaku.",
    
    # Row 92: "knp" -> "kenapa"
    92: "kenapa saya tidak bisa mengaktifkan paylater?",
    
    # Row 96: "bagaima" -> "bagaimana"
    96: "bagaimana cara beli pulsa",
    
    # Row 97: "knp" -> "kenapa", "says" -> "saya", "gabisa" -> "gak bisa", "dipake" -> "dipakai"
    97: "kenapa paylater saya gak bisa dipakai",
    
    # Row 98: "di tolak" -> "ditolak"
    98: "mengapa pinjaman saya selalu ditolak",
    
    # Row 100: "knp" -> "kenapa", "pijeman" -> "pinjaman"
    100: "kenapa gak bisa pinjaman",
    
    # Row 106: "knpa" -> "kenapa", "gk" -> "gak"
    106: "kenapa pinjaman gak bisa??",
    
    # Row 112: "cicicilan" -> "cicilan"
    112: "tidak bisa pakai cicilan beli data",
    
    # Row 113: "playleter sya" -> "paylater saya"
    113: "paylater saya kenapa gak bisa",
    
    # Row 114: "laku laku" -> "akulaku"
    114: "nah kenapa saya tidak bisa meminjam lagi di akulaku ini?",
    
    # Row 117: "keredit" -> "kredit"
    117: "bagaimana meningkatkan nilai kredit?",
    
    # Row 123: "yg" -> "yang"
    123: "apa yang menyebabkan pengajuan ditolak",
    
    # Row 128: "gk" -> "gak"
    128: "kenapa saya gak bisa ke halaman untuk bayar utang saya",
    
    # Row 141: "di pakai" -> "dipakai"
    141: "bagaimana cara saya belanja. sedangkan paylater tidak bisa dipakai",
    
    # Row 145: "payleter" -> "paylater", "di kendalikan" -> "digunakan"
    145: "kenapa paylater saya gak bisa digunakan",
    
    # Row 151: "minjam" -> "pinjam", "letter" -> "paylater"
    151: "pinjam uang paylater nya gagal terus.",
    
    # Row 152: "di berikan" -> "diberikan"
    152: "bisakah saya diberikan keringanan",
    
    # Row 160: "pusa" -> "pulsa"
    160: "beli pulsa saya.",
    
    # Row 162: "aku laku" -> "akulaku"
    162: "limit di akulaku saya tidak menambah bos. kenapa? padahal semua cicilan beres bos lancar.",
    
    # Row 163: "aku laku" -> "akulaku"
    163: "saya bayar lancar, semua tagihan di akulaku tetapi limitnya segitu segitu aja bos.",
    
    # Row 165: "bsa" -> "bisa", "bwt pajagan" -> "buat belanja"
    165: "kenapa paylater tidak bisa dipakai?? apa buat belanja",
    
    # Row 170: "playleter" -> "paylater"
    170: "mengapa saya tidak bisa menggunakan paylater",
    
    # Row 179: "payleter" -> "paylater"
    179: "ko paylater ga bisa dipakai ya",
    
    # Row 180: "disinya" -> "di sini"
    180: "uangnya ko belum masuk ka tapi di sini udah ada tagihan",
    
    # Row 182: "TDK" -> "tidak"
    182: "saya salah metode pembayaran kenapa tidak bisa diubah lagi",
    
    # Row 183: "dana cici" -> "dana cicil"
    183: "dana cicil limitnya cuman ada tiga juta setengah.",
    
    # Row 184: "di ubah" -> "diubah", "jd" -> "jadi"
    184: "apakah dana pembayaran dana flexi bisa diubah jadi dana cicil?",
    
    # Row 185: "gck" -> "gak", "data2" -> "data-data"
    185: "udah hapus aja data-data aku percuma gak bisa ngajuin limit pun gak ada.",
    
    # Row 193: "paletter" -> "paylater"
    193: "bayar tagihan paylater semuanya.",
    
    # Row 195: "play letter" -> "paylater"
    195: "tariklah barang barang ke dalam truk pengangkut. terima kasih anda telah menonton videonya. paylater nggak ada, ngajuin pun nggak bisa.",
    
    # Row 196: "byar" -> "bayar", "playleter" -> "paylater"
    196: "bayar lunas terus ngajuin pun gak bisa paylater pun gak ada",
    
    # Row 204: "payleter" -> "paylater", "gmn" -> "gimana"
    204: "bayar paylater gimana ya kalau bulan ini sudah bayar, saya mau bayar lagi untuk bulan berikutnya",
    
    # Row 209: "di gunakan" -> "digunakan"
    209: "Paylater saya tidak bisa digunakan",
    
    # Row 211: "tidak mbak tidak" -> "saya tidak"
    211: "kenapa saya tidak bisa bayar pln dari shopee later limit saya.",
    
    # Row 212: "di lamakan" -> "diperpanjang"
    212: "tenornya tolong diperpanjang min",
    
    # Row 213: "bagai mana" -> "bagaimana"
    213: "bagaimana cara meningkatkan kredit saya",
    
    # Row 215: "bagai mana" -> "bagaimana"
    215: "bagaimana meningkatkan batas kredit saya",
    
    # Row 218: "lewar" -> "lewat"
    218: "bayar tagihan lewat bca",
    
    # Row 219: "pembayan" -> "pembayaran"
    219: "pembayaran lewat bank bca",
    
    # Row 225: "paylaternga" -> "paylaternya"
    225: "kenapa paylaternya gak bisa dipakai",
    
    # Row 238: "d lakukan" -> "dilakukan"
    238: "kenapa pembayaran bulan ini udah dilakukan belum muncul transaksi lunas?",
    
    # Row 239: "men chek" -> "mengecek", "yg" -> "yang", "di kirimkan" -> "dikirimkan"
    239: "saya telah mengecek pesanan saya yang saya refund sepihak karena penjual tidak membalas chat saya dan barang tidak dikirimkan... namun refund tidak masuk ke akun saya. apa yang harus saya lakukan",
    
    # Row 240: "pay later" -> "paylater", "di pake" -> "dipakai"
    240: "payah paylater gak bisa dipakai",
    
    # Row 242: "diakulaku" -> "di akulaku"
    242: "gimana cara bayar di akulaku",
    
    # Row 244: "sken" -> "scan"
    244: "kenapa scan saya gagal terus",
    
    # Row 256: "ayo awal biar biar" -> "lebih awal biar"
    256: "bisakah saya membayar lebih awal biar mengurangi bunga.",
    
    # Row 261: "tagian" -> "tagihan"
    261: "periksa tagihan saya",
    
    # Row 265: "tidak bisa terus" -> "tidak lolos terus", "tempat waktu" -> "tepat waktu"
    265: "kenapa pinjaman saya tidak lolos terus padahal saya bayar tepat waktu",
    
    # Row 267: "byr" -> "bayar"
    267: "gagal bayar tagihan PDAM",
    
    # Row 272: "di tolak" -> "ditolak"
    272: "kenapa ditolak??",
    
    # Row 273: "sya" -> "saya", "yg" -> "yang"
    273: "jadi ini no rekening yang harus saya lunasi ka",
    
    # Row 277: "yg" -> "yang"
    277: "Minggu saya lunasin yang tagihan 345000 dulu ya Pak",
    
    # Row 278: "do.a in" -> "doain", "yg" -> "yang"
    278: "Minggu depan saya lunasin yang 345000 dulu. Pak, doain biar saya terus biar cepet lunas ga nyampai sebulan",
    
    # Row 280: "melakukam" -> "melakukan"
    280: "kenapa saya tidak bisa melakukan pembayaran melalui mandiri",
    
    # Row 283: "pinjem an" -> "pinjaman"
    283: "limit pinjaman masih 300 Pak",
    
    # Row 293: "yg" -> "yang"
    293: "saya lunas ya tagihan nya yang 336000",
    
    # Row 296: "tagin" -> "tagihan", "pake" -> "pakai", "ngk" -> "nggak"
    296: "kalo saya bayar tagihan pakai dana bisa nggak",
    
    # Row 304: "pinjma" -> "pinjam", "wktu" -> "waktu", "byr" -> "bayar", "lgi" -> "lagi"
    304: "kok saya ditolak ya mau pinjam lagi saya bayar ya sebelum waktu bayar saya sudah bayar tolong pertimbangkan lagi",
    
    # Row 306: "di tolak" -> "ditolak", "di acc" -> "di-acc"
    306: "kenapa sekarang pinjaman saya ditolak, sebelumnya selalu di acc",
    
    # Row 309: "di gunakan" -> "digunakan"
    309: "limit paylater saya tidak bisa digunakan",
    
    # Row 310: "rincuan" -> "rincian"
    310: "tolong berikan saya rincian pembayaran cicilan saya di pembiayaan toko",
    
    # Row 311: "e wallef" -> "e-wallet"
    311: "kenapa tidak bisa isi e-wallet",
    
    # Row 316: "bagaimaca" -> "bagaimana", "blum" -> "belum"
    316: "bagaimana cara melihat tagihan yang belum dibayar",
    
    # Row 318: "gemana" -> "gimana"
    318: "nomor kode Indomaret bener tapi tidak ada. Atas nama Wahyono gimana itu Pak",
    
    # Row 331: "kadoh" -> "kado"
    331: "ingin beli kado gak punya uang",
    
    # Row 337: "koe" -> "kok"
    337: "kok tidak ada bank bca ya",
    
    # Row 339: "di pake" -> "dipakai"
    339: "kenapa paylater saya tidak bisa dipakai",
    
    # Row 348: "tiba tiba" -> "tiba-tiba"
    348: "kenapa cicilan tiba-tiba ada dp sebelumnya nol dp?",
    
    # Row 350: "saldo ulang tahun" -> "kado ulang tahun"
    350: "beli kado ulang tahun untuk pacar saya.",
    
    # Row 352: "ktedit" -> "kredit"
    352: "berapa kredit skor saya",
    
    # Row 360: "mna" -> "mana"
    360: "mana kuota yang saya beli tadi",
    
    # Row 366: "upa apa" -> "apa"
    366: "apa kado buat pacar aku?",
    
    # Row 367: "di setujui" -> "disetujui"
    367: "kenapa tidak disetujui pengajuan",
    
    # Row 368: "piloter" -> "paylater"
    368: "apakah paylater bisa mengambil hp dengan kredit?",
    
    # Row 376: "di bantu" -> "dibantu", "nomer" -> "nomor"
    376: "selamat siang kak admin ijin boleh dibantu mengetahui nomor call center nya",
    
    # Row 380: "blm" -> "belum"
    380: "kemarin belum masuk uang di rekening saya coba nanti saya cek lagi",
    
    # Row 381: "blm" -> "belum"
    381: "saya cek di ATM BRI belum masuk uangnya",
    
    # Row 382: "tranfer" -> "transfer", "w a" -> "WA"
    382: "bukti transfer nya mana Pak, kirimkan ke WA saya",
    
    # Row 383: "reknngBRI" -> "rekening BRI", "tp" -> "tapi"
    383: "bisa, tapi belum masuk pinjamannya di rekening BRI saya",
    
    # Row 384: "KA knp BS kmbali" -> "ka kenapa bisa kembali"
    384: "ka kenapa saya tidak bisa mengajukan kembali",
    
    # Row 388: "kira kira" -> "kira-kira"
    388: "kalau saya lunasi empat bulan ini bisa ada pengurangan bunga enggak? dan limit bisa saya tarik kembali? kira-kira ada enggak lima belas juta?",
    
    # Row 397: "tahiham" -> "tagihan"
    397: "periksa tagihan saya",
    
    # Row 404: "bak aku laku" -> "di akulaku"
    404: "kenapa saya tidak bisa pinjam di akulaku padahal saya tepat bayar?",
    
    # Row 405: "pinjamam" -> "pinjaman"
    405: "pembatalan pinjaman",
    
    # Row 408: "di gunakan" -> "digunakan"
    408: "paylater ga bisa digunakan",
    
    # Row 410: "pay later" -> "paylater"
    410: "cara mengaktifkan verifikasi paylater",
    
    # Row 411: "peliter" -> "paylater"
    411: "cara mengaktifkan paylater?",
    
    # Row 412: "di tolak" -> "ditolak"
    412: "ditolak mulu kontol",
    
    # Row 423: "payltr" -> "paylater", "d gunakan" -> "digunakan", "atow" -> "atau", "bayarblistrik" -> "bayar listrik"
    423: "kenapa saldo paylater saya tidak bisa digunakan untuk isi pulsa atau bayar listrik",
    
    # Row 425: "di tolak" -> "ditolak"
    425: "kenapa pengajuan saya selalu ditolak",
    
    # Row 428: "aku laku pilotter" -> "akulaku paylater"
    428: "bisa nggak naikin limit akulaku paylater saya?",
    
    # Row 430: "payleter" -> "paylater"
    430: "saya sudah melakukan pembayaran paylater",
    
    # Row 431: "di bayar lgi" -> "dibayar lagi"
    431: "kalau saya bayar semua hutang saya. apakah bunga dibayar lagi",
    
    # Row 433: "sy" -> "saya", "mentor" -> "setor"
    433: "kemana saya harus setor pinjaman saya",
    
    # Row 434: "pay later" -> "paylater", "di pakai" -> "dipakai"
    434: "kenapa paylater saya tidak bisa dipakai",
    
    # Row 439: "knp sy TDK bisa d gunakan" -> full form
    439: "kenapa spaylater saya tidak bisa digunakan",
    
    # Row 440: "pay later" -> "paylater"
    440: "kenapa pengajuan pembayaran paylater token listrik saya gagal",
    
    # Row 444: "sp letter" -> "spaylater"
    444: "kenapa pinjaman spaylater saya tidak bisa digunakan?",
    
    # Row 445: "aspirator" -> "spaylater" (speech recognition error)
    445: "kenapa spaylater saya tidak bisa digunakan?",
    
    # Row 448: "lu di pulsa" -> "isi pulsa"
    448: "isi pulsa.",
    
    # Row 449: "play store terpusat" -> "paylater" (speech recognition error)
    449: "mengapa saya tidak bisa menggunakan paylater?",
    
    # Row 455: "ngak" -> "nggak"
    455: "saya udah bayar paylater kok nggak masuk",
    
    # Row 457: "aph kah klo" -> "apakah kalau", "bbisa" -> "bisa"
    457: "halo apakah kalau aku ngajuan bisa diterima",
    
    # Row 459: "di gunakan" -> "digunakan"
    459: "ko paylater tidak bisa digunakan untuk scan barcode",
    
    # Row 460: "di ambil" -> "diambil"
    460: "kenapa paylater dan pinjaman saya tidak bisa diambil?",
    
    # Row 463: "sy" -> "saya"
    463: "apakah saya bisa membayar lebih awal",
    
    # Row 464: "paletter" -> "paylater"
    464: "kenapa kalau sudah pesan satu barang di paylater tidak bisa pesan lagi?",
    
    # Row 469: "puasa" -> "pulsa" (the user's example!)
    469: "isi pulsa saya.",
    
    # Row 470: "limat" -> "limit"
    470: "kenapa paylater saya tidak bisa digunakan, padahal limit ada",
}


def apply_typo_corrections(df_clean):
    """
    Apply typo corrections to df_clean.
    
    The '原始语音' column (3rd column) contains the original text.
    The 'Kalimat (fixed)' column (4th column) will contain the corrected text.
    
    For rows WITH typos: the corrected text is written to 'Kalimat (fixed)'.
    For rows WITHOUT typos: the original text is copied to 'Kalimat (fixed)'.
    
    Parameters:
        df_clean: pandas DataFrame with columns '序号', '原始语音', 'Kalimat (fixed)'
        
    Returns:
        df_clean: DataFrame with 'Kalimat (fixed)' populated
    """
    col_orig = '原始语音'
    col_fixed = 'Kalimat (fixed)'
    col_seq = '序号'
    
    for seq_no, corrected_text in typo_corrections.items():
        mask = df_clean[col_seq].astype(str) == str(seq_no)
        if mask.any():
            df_clean.loc[mask, col_fixed] = corrected_text
        else:
            print(f"WARNING: Could not find row with {col_seq}={seq_no}")
    
    # For rows without typos, copy the original text
    mask_no_fix = df_clean[col_fixed].isna()
    df_clean.loc[mask_no_fix, col_fixed] = df_clean.loc[mask_no_fix, col_orig]
    
    return df_clean


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    
    # Read the CSV
    df = pd.read_csv('temp/ai语音数据 - Sheet1.csv')
    
    # Drop the first row (URL, not data)
    df_clean = df.drop(index=0).reset_index(drop=True)
    
    # Apply corrections
    df_clean = apply_typo_corrections(df_clean)
    
    # Summary
    col_orig = '原始语音'
    col_fixed = 'Kalimat (fixed)'
    
    total = len(df_clean)
    fixed_rows = df_clean[df_clean[col_fixed] != df_clean[col_orig]]
    
    print(f"Total rows: {total}")
    print(f"Rows with typo corrections: {len(fixed_rows)}")
    print(f"Rows without changes: {total - len(fixed_rows)}")
    
    # Save
    df_clean.to_csv('temp/ai语音数据_fixed.csv', index=False, encoding='utf-8-sig')
    print(f"\nSaved corrected data to temp/ai語音数据_fixed.csv")
    
    # Print corrections
    print(f"\n{'='*80}")
    print("CORRECTIONS:")
    print(f"{'='*80}")
    for _, row in fixed_rows.iterrows():
        print(f"\nRow {row['序号']}:")
        print(f"  ORIGINAL: {row[col_orig]}")
        print(f"  FIXED:    {row[col_fixed]}")
