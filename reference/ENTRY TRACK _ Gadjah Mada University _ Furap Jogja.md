Berdasarkan dokumen MaternaLink yang Anda upload, berikut rancangan lengkap untuk Section 2, 3, dan 4 yang terstruktur dan siap digunakan:

---

## SECTION 2: TECHNICAL ARCHITECTURE

### 2.1 System Components

**Inputs:**

- **Real-time operational data** dari \~30 puskesmas per IFK: stok obat maternal (oksitosin, misoprostol, MgSO4), LPLPO reports, consumption logs  
- **External streaming data**: cuaca/monsoon forecasts, transport disruption alerts, emergency spikes (bencana, wabah)  
- **User inputs**: manual stock reports (offline-first mobile), case escalation notes, feedback dari bidan/petugas kesehatan  
- **Historical data**: 2-3 tahun data konsumsi obat, seasonal patterns, MMR statistics per wilayah

**Processing Core:**

- **Cloud-based AI Pipeline** (AWS/GCP Indonesia region) dengan hybrid edge computing untuk daerah dengan konektivitas terbatas  
- **AI Schema Harmonization Engine**: menyeragamkan format data dari berbagai sistem legacy kesehatan daerah  
- **Probabilistic Demand Forecasting Module**: Time-series forecasting dengan uncertainty quantification  
- **Adaptive Buffer Planning Engine**: dynamic safety stock calculation berdasarkan risk scoring  
- **Explainable Allocation Recommender**: XAI-driven decision support untuk distribusi obat yang adil dan transparan

**Outputs:**

- **Dashboard IFK-level**: real-time visibility stok, depletion alerts 7-14 hari ke depan, heatmap risk wilayah  
- **Allocation recommendations**: rekomendasi redistribusi obat antar-puskesmas dengan justification (explainable AI)  
- **Automated LPLPO workflows**: laporan otomatis ke Dinas Kesehatan, early warning ke Kementerian Kesehatan  
- **Offline-sync mobile alerts**: notifikasi stok kritis untuk bidan di daerah terpencil (via SMS/push notification)

### 2.2 Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              MATERNA LINK SYSTEM                            │
│                         Hub-and-Spoke Intelligence Model                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐ │
│   │  Puskesmas  │    │  Puskesmas  │    │  Puskesmas  │    │   Klinik    │ │
│   │   (Spoke)   │    │   (Spoke)   │    │   (Spoke)   │    │   (Spoke)   │ │
│   │  ~30 units  │    │  ~30 units  │    │  ~30 units  │    │   ~5 units  │ │
│   └──────┬──────┘    └──────┬──────┘    └──────┬──────┘    └──────┬──────┘ │
│          │                  │                  │                  │        │
│          └──────────────────┴──────────────────┘──────────────────┘        │
│                                     │                                       │
│                    ┌────────────────┴────────────────┐                      │
│                    │      OFFLINE-FIRST SYNC LAYER     │                      │
│                    │    (Edge Computing / Mobile App)  │                      │
│                    └────────────────┬────────────────┘                      │
│                                     │                                       │
│   ┌─────────────────────────────────┴─────────────────────────────────────┐ │
│   │                         IFK HUB (Cloud)                               │ │
│   │  ┌─────────────────────────────────────────────────────────────────┐  │ │
│   │  │              DATA INTEGRATION & SCHEMA HARMONIZATION            │  │ │
│   │  │         (ETL Pipeline + FHIR-compliant Data Lake)               │  │ │
│   │  └─────────────────────────────────────────────────────────────────┘  │ │
│   │                              │                                        │ │
│   │  ┌───────────────────────────┼─────────────────────────────────────┐  │ │
│   │  │                           ▼                                     │  │ │
│   │  │  ┌─────────────┐  ┌──────────────┐  ┌──────────────────────┐  │  │ │
│   │  │  │  Real-time  │  │   Weather/   │  │   Emergency/Event    │  │  │ │
│   │  │  │  Stock Data │  │  Transport   │  │     Detection        │  │  │ │
│   │  │  │   Stream    │  │    APIs      │  │   (News/Satellite)   │  │  │ │
│   │  │  └──────┬──────┘  └──────┬───────┘  └──────────┬───────────┘  │  │ │
│   │  │         └─────────────────┴─────────────────────┘              │  │ │
│   │  │                              │                                 │  │ │
│   │  │                    ┌─────────▼──────────┐                      │  │ │
│   │  │                    │   AI PROCESSING    │                      │  │ │
│   │  │                    │      CORE          │                      │  │ │
│   │  │         ┌──────────┴────────────────────┴──────────┐           │  │ │
│   │  │         │                                          │           │  │ │
│   │  │  ┌──────▼──────┐  ┌──────────▼──────────┐  ┌──────▼──────┐   │  │ │
│   │  │  │  Demand     │  │  Adaptive Buffer    │  │ Explainable │   │  │ │
│   │  │  │ Forecasting │  │  Planning Engine    │  │ Allocation  │   │  │ │
│   │  │  │  (Prophet/  │  │  (Risk Scoring +    │  │ Recommender │   │  │ │
│   │  │  │   LSTM)     │  │   Safety Stock)     │  │  (SHAP/XAI) │   │  │ │
│   │  │  └──────┬──────┘  └──────────┬──────────┘  └──────┬──────┘   │  │ │
│   │  │         └────────────────────┴─────────────────────┘           │  │ │
│   │  │                              │                                 │  │ │
│   │  │                    ┌─────────▼──────────┐                      │  │ │
│   │  │                    │   DECISION SUPPORT │                      │  │ │
│   │  │                    │     DASHBOARD      │                      │  │ │
│   │  │                    └─────────┬──────────┘                      │  │ │
│   │  └──────────────────────────────┼─────────────────────────────────┘  │ │
│   └─────────────────────────────────┼─────────────────────────────────────┘ │
│                                     │                                       │
│   ┌─────────────────────────────────┼─────────────────────────────────────┐ │
│   │                                 ▼                                     │ │
│   │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │ │
│   │  │   IFK Staff │  │  Dinas      │  │  Kemenkes   │  │  Puskesmas  │  │ │
│   │  │  (Decision) │  │  Kesehatan  │  │  (Policy)   │  │  (Action)   │  │ │
│   │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │ │
│   └───────────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## SECTION 3: AI APPROACH & MODEL SELECTION

### Primary AI Approach

- [x] **Machine Learning** (Time-series forecasting, probabilistic modeling)  
- [x] **NLP** (Schema harmonization, automated report parsing, chatbot untuk feedback bidan)  
- [ ] Computer Vision  
- [ ] Generative AI  
- [x] **Other: Operations Research** (Optimization untuk allocation planning)

### Model Selection

| Komponen | Model/Framework | Implementasi |
| :---- | :---- | :---- |
| **Demand Forecasting** | **Prophet** (Meta) \+ **LSTM/GRU** (TensorFlow/Keras) | Hybrid approach: Prophet untuk seasonal decomposition \+ LSTM untuk pattern kompleks dan uncertainty quantification |
| **Schema Harmonization** | **Hugging Face Transformers** (BERT-based) \+ **Rule-based ETL** | NLP untuk mapping field non-standar dari berbagai sistem daerah ke FHIR standard |
| **Risk Scoring & Buffer Planning** | **XGBoost/LightGBM** \+ **Monte Carlo Simulation** | Prediksi probabilitas stockout berdasarkan multi-faktor (cuaca, transport, seasonal) |
| **Explainable Allocation** | **LLM** | Generative AI bridges the gap between complex ML outputs and human decision-makers by providing explainable reasoning for distribution allocations, ensuring IFK staff trust the AI's recommendations.  |
| **Anomaly Detection** | **Isolation Forest** \+ **Statistical Process Control** | Deteksi consumption spikes (emergency, fraud, atau data error) |

### Reasoning

**Mengapa hybrid Prophet+LSTM untuk forecasting:**

1. **Prophet** optimal untuk data dengan strong seasonality (monsoon patterns, holiday effects) dan missing values yang umum di data kesehatan daerah Indonesia  
2. **LSTM** menangkap non-linear dependencies dan long-term trends yang kompleks  
3. **Uncertainty quantification** krusial untuk maternal medicine—kesalahan forecasting bisa berarti nyawa. Probabilistic forecast memberikan range confidence, bukan single point estimate

**Mengapa XGBoost untuk risk scoring:**

- Handle tabular data dengan mixed types (categorical: jenis obat, wilayah; numerical: stok, lead time)  
- Robust terhadap outliers (data lapangan sering tidak bersih)  
- Feature importance natively tersedia untuk explainability

**Mengapa LLM untuk explainability:**

- Stakeholder kesehatan (bukan data scientist) memerlukan justifikasi dalam bahasa natural (natural language) MENGAPA AI merekomendasikan redistribusi obat ke Puskesmas A vs B.  
- LLM, sebagai Generative AI, menjembatani output kompleks dari ML (seperti hasil SHAP atau XGBoost) ke bahasa manusia, yang penting untuk memastikan staf IFK mempercayai dan menggunakan rekomendasi alokasi.  
- LLM dapat memberikan penjelasan lokal (local explanation) dan ringkas per keputusan, kritis untuk akuntabilitas dalam distribusi sumber daya publik.

---

## SECTION 4: DATA STRATEGY & ETHICS

### Data Sources

| Sumber | Jenis Data | Akses |
| :---- | :---- | :---- |
| **Open Data Kemenkes** | LPLPO reports, MMR statistics, obat essential lists | Portal Satu Sehat Kemenkes (public API) |
| **WHO/UNICEF Maternal Health Datasets** | Benchmark consumption rates, global stockout indicators | WHO IRIS, UNICEF Data Warehouse (open license) |
| **BMKG Weather API** | Curah hujan, cuaca ekstrem, prediksi monsoon | API terbuka BMKG |
| **Synthetic Data** | Augmentasi untuk wilayah dengan data historis minimal (Papua, Maluku) | Dibuat menggunakan CTGAN berdasarkan distribusi statistik wilayah serupa |
| **Custom Collection (Pilot)** | Data operasional 3-5 IFK mitra di Yogyakarta/DIY sebagai proof-of-concept | MoU dengan Dinas Kesehatan DIY |

### Data Quality & Cleaning

1. **Schema Validation Pipeline**: Automated check FHIR compliance, flag missing mandatory fields (nama obat, quantity, tanggal)  
2. **Outlier Detection**: Isolation Forest untuk identifikasi consumption values yang tidak realistis (data entry error atau fraud)  
3. **Temporal Consistency**: Cek logical sequence (stok akhir bulan ≠ stok awal bulan berikutnya → flag untuk verifikasi)  
4. **Imputation Strategy**:  
   - Mean/median imputation untuk data numerik sederhana  
   - KNN imputation untuk pattern kompleks  
   - **Tidak imputasi** untuk periode stockout yang terverifikasi (nilai 0 adalah valid, bukan missing)  
5. **Human-in-the-loop Validation**: Dashboard untuk petugas IFK memverifikasi data flagged oleh sistem sebelum masuk training pipeline

### Licensing & Legality

| Dataset | Lisensi | Kelayakan Hackathon |
| :---- | :---- | :---- |
| Data Kemenkes (Satu Sehat) | **Open Government License** | ✅ Diperbolehkan untuk riset dan pengembangan solusi kesehatan publik |
| WHO Maternal Health Reports | **CC BY-NC-SA 3.0 IGO** | ✅ Non-commercial research allowed |
| BMKG Weather Data | **Terbuka untuk publik** | ✅ Bebas digunakan |
| Synthetic Data (CTGAN) | **Generated internally** | ✅ Full ownership team |
| Pilot Data DIY | **MoU dengan Dinas Kesehatan** | ✅ Ethical clearance dan data anonymization sesuai PERMENKES No. 24/2022 |

**Catatan keamanan:** Semua data personal (nama pasien, NIK) di-*hash* dan di-*anonymize* sebelum masuk pipeline. Hanya aggregate data (stok per puskesmas, consumption per wilayah) yang digunakan untuk AI training.

### Bias Mitigation & Fairness

**Identifikasi Bias Potensial:**

1. **Regional Bias**: Data dari Jawa (Yogyakarta) jauh lebih lengkap dibanding Papua/Maluku → model mungkin underperform untuk wilayah timur Indonesia  
2. **Reporting Bias**: Puskesmas dengan infrastruktur digital lebih baik melaporkan data lebih sering → menciptakan false sense of security untuk puskesmas offline  
3. **Seasonal Bias**: Monsoon mempengaruhi data collection (reporting delay) → bukan hanya consumption yang menurun

**Strategi Mitigasi:**

| Bias | Strategi |
| :---- | :---- |
| **Regional** | **Stratified sampling** dengan oversampling data dari wilayah underrepresented (Papua, Maluku, NTT). **Transfer learning**: train di Jawa, fine-tune dengan limited real data dari timur Indonesia \+ synthetic data |
| **Reporting** | **Offline-first design**: sistem tidak mengasumsikan "no report \= no problem". Missing reports trigger escalation, bukan imputasi otomatis. **Confidence scoring**: rekomendasi untuk puskesmas dengan data sparse diberi flag "low confidence—verifikasi manual" |
| **Seasonal/Temporal** | **Feature engineering**: pisahkan "true zero consumption" vs "missing due to monsoon". Gunakan weather data sebagai covariate dalam forecasting |
| **Gender** | Walaupun fokus maternal health, pastikan tidak ada bias dalam resource allocation antar jenis kelamin. **Fairness metrics**: cek allocation equity score antar puskesmas (tidak hanya berdasarkan volume, tapi juga MMR/kebutuhan) |
| **Linguistic** | **Multilingual schema mapping**: dukung input dalam Bahasa Indonesia daerah (misal: "ubat" untuk obat di beberapa daerah). NLP model dilatih dengan mixed Indonesian dialects |

**Fairness Monitoring:**

- **Demographic parity**: Allocation recommendation rate tidak berbeda signifikan antar wilayah dengan karakteristik serupa  
- **Calibration**: Prediksi probabilitas stockout akurat untuk semua wilayah (bukan hanya Jawa)  
- **Regular audit**: Quarterly bias audit dengan melibatkan stakeholder dari wilayah timur Indonesia

---

Apakah perlu saya tambahkan detail implementasi teknis lebih lanjut atau sesuaikan format untuk submission PDF (maksimal 5 halaman)?  
