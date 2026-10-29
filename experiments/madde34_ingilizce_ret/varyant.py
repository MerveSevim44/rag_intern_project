"""
Madde 34 — #82 cevap chunk'ının (4185, Fourier sayfa 12) izole varyantları.

src/ ve rag.db değişmez; varyantlar yalnız 4185'in METNİNİ değiştirir, bağlamın
diğer chunk'ları ve sırası aynı kalır (retrieval değil, üretim ölçülüyor).

  V0  DB'deki metin (İngilizce gövde, Symbol fontu PUA karakterleri, parantezler
      ayrı satırda)
  A1  yalnız mekanik sembol eşlemesi: U+F0xx -> Adobe Symbol glifi (δ, ω, ∫, ( )…);
      satır düzeni aynı. Uygulanabilir bir son işlemenin üst sınırı.
  A2  formüller elle yeniden kurulmuş, gövde İngilizce (sembol tavanı)
  B   gövde Türkçe, formül satırları DB'deki gibi (PUA, parçalı)
  C   gövde Türkçe + formüller elle kurulmuş (A2 + B; tavan)

Elle kurulan formüller PDF sayfa 12 ile GT referansından (y(t)=f(t)cos(ω0t),
Y(ω) = (1/2π) F(ω) ∗ (πδ(ω+ω0) + πδ(ω−ω0)), δ kaydırma özelliği;
A1 çıktısıyla satır satır karşılaştırıldı).
"""

CEVAP_ID = 4185

# Adobe Symbol encoding (yalnız bu PDF'te görülen ve yaygın kod noktaları).
SYMBOL = {
    0x28: "(", 0x29: ")", 0x2A: "∗", 0x2B: "+", 0x2D: "−", 0x3D: "=",
    0x61: "α", 0x62: "β", 0x64: "δ", 0x44: "Δ", 0x65: "ε", 0x66: "φ", 0x67: "γ",
    0x6A: "j", 0x6C: "λ", 0x70: "π", 0x71: "θ", 0x73: "σ", 0x74: "τ", 0x77: "ω",
    0x57: "Ω", 0x53: "Σ", 0xA3: "≤", 0xA5: "∞", 0xAE: "→", 0xB1: "±", 0xB3: "≥",
    0xB4: "×", 0xB6: "∂", 0xB9: "≠", 0xD0: "∠", 0xD6: "√", 0xE5: "Σ", 0xF2: "∫",
    0xE6: "", 0xE7: "", 0xE8: "", 0xF6: "", 0xF7: "", 0xF8: "",  # büyük parantez parçaları
    0xEC: "", 0xED: "", 0xEE: "", 0xEF: "", 0xFC: "", 0xFD: "", 0xFE: "",
}


def pua_esle(metin):
    """U+F000–U+F0FF -> Symbol glifi; tabloda olmayan kod noktası olduğu gibi kalır."""
    return "".join(SYMBOL.get(ord(ch) - 0xF000, ch) if 0xF000 <= ord(ch) <= 0xF0FF else ch
                   for ch in metin)


A2 = """Sinuzoidal Genlik Modülasyonu
(Sinusoidal Amplitude Modulation)
y(t) = f(t) cos(ω0 t)
Multiplication in the time domain is
convolution in the frequency domain :
Y(ω) = (1/2π) F(ω) ∗ (πδ(ω + ω0) + πδ(ω − ω0))
Recall that
x(t) ∗ δ(t) = ∫_{−∞}^{∞} δ(τ) x(t − τ) dτ = x(t)
x(t) ∗ δ(t − t0) = ∫_{−∞}^{∞} δ(τ − t0) x(t − τ) dτ = x(t − t0)
So,
Y(ω) = (1/2) F(ω + ω0) + (1/2) F(ω − ω0)
12"""

C = """Sinuzoidal Genlik Modülasyonu
(Sinüzoidal Genlik Modülasyonu)
y(t) = f(t) cos(ω0 t)
Zaman domenindeki çarpım,
frekans domeninde konvolüsyondur:
Y(ω) = (1/2π) F(ω) ∗ (πδ(ω + ω0) + πδ(ω − ω0))
Hatırlayın:
x(t) ∗ δ(t) = ∫_{−∞}^{∞} δ(τ) x(t − τ) dτ = x(t)
x(t) ∗ δ(t − t0) = ∫_{−∞}^{∞} δ(τ − t0) x(t − τ) dτ = x(t − t0)
Dolayısıyla,
Y(ω) = (1/2) F(ω + ω0) + (1/2) F(ω − ω0)
12"""

# B: V0'ın İngilizce satırları Türkçeye; formül satırları DB metninden aynen.
B_CEVIRI = {
    "(Sinusoidal Amplitude Modulation)": "(Sinüzoidal Genlik Modülasyonu)",
    "Multiplication in the time domain is": "Zaman domenindeki çarpım,",
    "convolution in the frequency domain :": "frekans domeninde konvolüsyondur:",
    "Recall that": "Hatırlayın:",
    "So,": "Dolayısıyla,",
}


def metin(varyant, v0):
    if varyant == "V0":
        return v0
    if varyant == "A1":
        return pua_esle(v0)
    if varyant == "A2":
        return A2
    if varyant == "B":
        satirlar = v0.split("\n")
        eksik = set(B_CEVIRI) - set(satirlar)
        assert not eksik, f"çevrilecek satır DB metninde yok: {eksik}"
        return "\n".join(B_CEVIRI.get(s, s) for s in satirlar)
    if varyant == "C":
        return C
    raise ValueError(varyant)
