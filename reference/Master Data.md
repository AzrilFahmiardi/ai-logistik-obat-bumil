### **Tabel Master**

1. #### **master\_puskesmas**

| Kolom | Tipe | Contoh | Keterangan |
| ----- | ----- | ----- | ----- |
| puskesmas\_id | VARCHAR(10) | PKM-001 | PK |
| nama | VARCHAR(100) | Puskesmas Lembah Sari |  |
| kabupaten\_kota | VARCHAR(100) | Kab. Manggarai |  |
| provinsi | VARCHAR(100) | NTT |  |
| tipe | ENUM | terpencil / sangat\_terpencil |  |
| status\_endemis\_malaria | BOOLEAN | true |  |
| ketersediaan\_lab | BOOLEAN | false |  |
| ketersediaan\_cold\_chain | BOOLEAN | false |  |
| kapasitas\_simpan\_obat | INTEGER | 500 | unit |
| jarak\_ke\_ifk\_km | FLOAT | 85.5 | km |
| lead\_time\_hari | FLOAT | 7.0 | hari |
| skor\_aksesibilitas | INTEGER | 1 | 1=buruk, 3=baik |
| aksesibilitas\_musim\_hujan | ENUM | terputus / terganggu / normal |  |

2. #### **master\_obat**

| Kolom | Tipe | Contoh | Keterangan |
| ----- | ----- | ----- | ----- |
| obat\_id | VARCHAR(10) | OBT-001 | PK |
| nama\_obat | VARCHAR(100) | Nifedipin |  |
| kategori | ENUM | darurat / esensial / rutin | Urgensi |
| tipe | ENUM | universal / tambahan |  |
| satuan | VARCHAR(20) | tablet |  |
| butuh\_cold\_chain | BOOLEAN | false |  |
| dosis\_standar\_harian | FLOAT | 3.0 | tablet/hari |
| durasi\_pengobatan\_hari | INTEGER | 14 | standar |

3. #### **knowledge\_base\_kondisi\_obat**

| Kolom | Tipe | Contoh | Keterangan |
| ----- | ----- | ----- | ----- |
| kb\_id | INTEGER | 1 | PK |
| kondisi | VARCHAR(100) | Preeklampsia |  |
| obat\_id | FK → master\_obat | OBT-003 |  |
| trimester\_applicable | VARCHAR(10) | T2,T3 |  |
| prioritas | INTEGER | 1 | 1=utama, 2=alternatif |
| catatan | TEXT | MgSO4 untuk kejang |  |

4. #### **knowledge\_base\_gejala\_kondisi**

| Kolom | Tipe | Contoh | Keterangan |
| ----- | ----- | ----- | ----- |
| gk\_id | INTEGER | 1 | PK |
| gejala | VARCHAR(100) | Bengkak wajah/kaki |  |
| kondisi | VARCHAR(100) | Preeklampsia |  |
| prior\_probability | FLOAT | 0.6 | Base probability |
| bobot\_tanpa\_lab | FLOAT | 0.8 | Naik jika tak ada lab |

### **Tabel Input (Transaksional)**

5. #### **input\_diagnosis\_periode**

| Kolom | Tipe | Contoh | Keterangan |
| ----- | ----- | ----- | ----- |
| id | SERIAL | 1 | PK |
| puskesmas\_id | FK | PKM-001 |  |
| periode | DATE | 2025-03-01 | Awal bulan |
| kondisi | VARCHAR(100) | Malaria |  |
| jumlah\_ibu | INTEGER | 5 |  |
| sumber\_diagnosis | ENUM | lab / klinis / rdt |  |

6. #### **input\_gejala\_periode**

| Kolom | Tipe | Contoh | Keterangan |
| ----- | ----- | ----- | ----- |
| id | SERIAL | 1 | PK |
| puskesmas\_id | FK | PKM-001 |  |
| periode | DATE | 2025-03-01 |  |
| gejala | VARCHAR(100) | Demam tinggi |  |
| jumlah\_ibu | INTEGER | 4 |  |

7. #### **input\_anamnesis\_raw**

| Kolom | Tipe | Contoh | Keterangan |
| ----- | ----- | ----- | ----- |
| id | SERIAL | 1 | PK |
| puskesmas\_id | FK | PKM-001 |  |
| periode | DATE | 2025-04-01 |  |
| audio\_path | VARCHAR(255) | /audio/pkm001\_202504\_001.webm | Path file audio |
| transkrip | TEXT | "Ibu bilang sudah 3 hari demam tinggi..." | Output Whisper |
| gejala\_extracted | JSON | \[{"gejala": "Demam tinggi", "confidence": 0.95}\] | Output NLP |
| gejala\_validated | JSON | \[{"gejala": "Demam tinggi", "confirmed": true}\] | Setelah validasi bidan |
| stt\_model | VARCHAR(50) | whisper-small | Model yang digunakan |
| extraction\_model | VARCHAR(50) | bert-ner-symptom | Model NER |
| created\_at | TIMESTAMP | 2025-04-15 10:30:00 |  |

8. #### **input\_konteks\_periode**

| Kolom | Tipe | Contoh | Keterangan |
| ----- | ----- | ----- | ----- |
| id | SERIAL | 1 | PK |
| puskesmas\_id | FK | PKM-001 |  |
| periode | DATE | 2025-03-01 |  |
| jumlah\_bumil\_t1 | INTEGER | 10 |  |
| jumlah\_bumil\_t2 | INTEGER | 15 |  |
| jumlah\_bumil\_t3 | INTEGER | 12 |  |
| musim | ENUM | hujan / kemarau |  |
| status\_klb | BOOLEAN | false |  |
| riwayat\_stockout\_6bln | JSON | {"OBT-001": 2} |  |

9. #### **input\_stok\_puskesmas**

| Kolom | Tipe | Contoh | Keterangan |
| ----- | ----- | ----- | ----- |
| id | SERIAL | 1 | PK |
| puskesmas\_id | FK | PKM-001 |  |
| periode | DATE | 2025-03-01 |  |
| obat\_id | FK | OBT-001 |  |
| stok\_awal | INTEGER | 100 |  |
| konsumsi\_periode | INTEGER | 80 |  |
| stok\_akhir | INTEGER | 20 |  |

### **Tabel Output**

10. #### **output\_prediksi\_stok**

| Kolom | Tipe | Contoh | Keterangan |
| ----- | ----- | ----- | ----- |
| id | SERIAL | 1 | PK |
| puskesmas\_id | FK | PKM-001 |  |
| periode\_prediksi | DATE | 2025-04-01 |  |
| obat\_id | FK | OBT-001 |  |
| kondisi\_terkait | VARCHAR(100) | Malaria |  |
| jumlah\_pasien\_estimasi | INTEGER | 7 |  |
| kebutuhan\_obat | INTEGER | 210 | pasien×dosis×durasi |
| buffer\_persen | FLOAT | 20.0 |  |
| total\_rekomendasi | INTEGER | 252 |  |
| confidence\_score | FLOAT | 0.75 |  |
| confidence\_level | ENUM | high / medium / low |  |

11. #### **output\_lplpo\_prediktif**

| Kolom | Tipe | Contoh | Keterangan |
| ----- | ----- | ----- | ----- |
| id | SERIAL | 1 | PK |
| puskesmas\_id | FK | PKM-001 |  |
| periode | DATE | 2025-04-01 |  |
| obat\_id | FK | OBT-001 |  |
| stok\_saat\_ini | INTEGER | 20 |  |
| kebutuhan\_prediksi | INTEGER | 252 |  |
| jumlah\_diminta | INTEGER | 232 | kebutuhan \- stok |
| days\_of\_stock | FLOAT | 3.5 |  |
| prioritas | ENUM | darurat / esensial / rutin |  |

12. #### **log\_rekonsiliasi**

| Kolom | Tipe | Contoh | Keterangan |
| ----- | ----- | ----- | ----- |
| id | SERIAL | 1 | Feedback loop |
| puskesmas\_id | FK | PKM-001 |  |
| periode | DATE | 2025-03-01 |  |
| obat\_id | FK | OBT-001 |  |
| prediksi | INTEGER | 252 |  |
| aktual | INTEGER | 230 |  |
| deviasi\_persen | FLOAT | 9.5 |  |

### **Referensi Master Data Lengkap**

#### **Daftar Lengkap Kondisi/Diagnosis**

| Kode | Kondisi | Kategori | Sumber Diagnosis |
| ----- | ----- | ----- | ----- |
| K01 | Malaria | Infeksi Parasit | RDT / Hasil lab |
| K02 | Anemia | Hematologi | Hasil lab HB |
| K03 | Hipertensi / Preeklampsia | Kardiovaskular | Pemeriksaan fisik ANC |
| K04 | Diabetes Gestasional | Metabolik | Tes gula darah |
| K05 | ISK (Infeksi Saluran Kemih) | Infeksi Bakteri | Diagnosis bidan/dokter |
| K06 | Infeksi Vagina (Vaginosis/Kandidiasis) | Infeksi | Diagnosis bidan/dokter |
| K07 | Hipotiroid | Endokrin | Diagnosis dokter |
| K08 | HIV | Infeksi Virus | RDT HIV / VCT |
| K09 | Hepatitis B | Infeksi Virus | RDT HBsAg |
| K10 | Toksoplasmosis | Infeksi Parasit | Serologi |
| K11 | ISPA / Pneumonia | Respirasi | Diagnosis bidan/dokter |
| K12 | Depresi / Kecemasan Antenatal | Mental Health | Skrining EPDS |
| K13 | Heartburn / GERD | Gastrointestinal | Anamnesis |
| K14 | Konstipasi / Wasir | Gastrointestinal | Anamnesis |

#### **Daftar Lengkap Gejala** 

| Kode | Gejala | Kemungkinan Kondisi |
| ----- | ----- | ----- |
| G01 | Demam tinggi | K01 Malaria, K11 ISPA, K05 ISK |
| G02 | Menggigil | K01 Malaria |
| G03 | Mual / muntah berlebihan | Hiperemesis, K01 Malaria, K09 Hepatitis |
| G04 | Lemas / mudah lelah ekstrem | K02 Anemia, K07 Hipotiroid, K01 Malaria |
| G05 | Pusing / sakit kepala berat | K02 Anemia, K03 Preeklampsia, Hipertensi |
| G06 | Bengkak wajah / kaki | K03 Preeklampsia, Gagal ginjal |
| G07 | Nyeri / panas saat kencing | K05 ISK |
| G08 | Keputihan abnormal | K06 Vaginosis, Kandidiasis |
| G09 | Penglihatan kabur | K03 Preeklampsia (tanda bahaya) |
| G10 | Nyeri ulu hati | K13 GERD, K03 Preeklampsia berat |
| G11 | Sesak napas | K02 Anemia berat, K11 Pneumonia |
| G12 | Kulit / mata kuning | K09 Hepatitis B |
| G13 | Kram kaki / nyeri tulang | Kekurangan Kalsium |
| G14 | Sedih berkepanjangan / cemas | K12 Depresi Antenatal |
| G15 | Susah BAB / perut kembung | K14 Konstipasi, K07 Hipotiroid |

#### **Daftar Lengkap Obat Tambahan**

| Kode | Nama Obat | Kategori | Satuan | Untuk Kondisi |
| ----- | ----- | ----- | ----- | ----- |
| OBT-001 | Kina | esensial | tablet | K01 Malaria (T1) |
| OBT-002 | Klindamisin | esensial | kapsul | K01 Malaria (T1) |
| OBT-003 | ACT (Artemisinin Combination Therapy) | esensial | tablet | K01 Malaria (T2-T3) |
| OBT-004 | Fe dosis tinggi | esensial | tablet | K02 Anemia berat, Komplikasi Malaria |
| OBT-005 | Vitamin B12 | rutin | tablet | K02 Anemia berat |
| OBT-006 | Folat tambahan | rutin | tablet | K02 Anemia berat |
| OBT-007 | Glukosa oral / IV | darurat | vial | Komplikasi Malaria (hipoglikemia) |
| OBT-008 | Nifedipin | esensial | tablet | K03 Hipertensi |
| OBT-009 | Metildopa | esensial | tablet | K03 Hipertensi |
| OBT-010 | MgSO4 (Magnesium Sulfat) | darurat | vial | K03 Preeklampsia (kejang) |
| OBT-011 | Insulin | darurat | vial | K04 Diabetes Gestasional |
| OBT-012 | Metformin | esensial | tablet | K04 Diabetes Gestasional |
| OBT-013 | Amoksisilin | esensial | kapsul | K05 ISK, K11 ISPA, Komplikasi DM |
| OBT-014 | Sefaleksin | esensial | kapsul | K05 ISK, Komplikasi DM |
| OBT-015 | Ondansetron | esensial | tablet | Hiperemesis Gravidarum |
| OBT-016 | Vitamin B6 (Piridoksin) | rutin | tablet | Hiperemesis Gravidarum |
| OBT-017 | Antasida | rutin | tablet | Hiperemesis, K13 GERD |
| OBT-018 | Levotiroksin | esensial | tablet | K07 Hipotiroid |
| OBT-019 | ARV (Antiretroviral) | darurat | tablet | K08 HIV |
| OBT-020 | Kotrimoksazol | esensial | tablet | K08 HIV (profilaksis) |
| OBT-021 | Tenofovir | esensial | tablet | K09 Hepatitis B |
| OBT-022 | Metronidazol | esensial | tablet | K06 Vaginosis |
| OBT-023 | Klotrimazol topikal | rutin | tube | K06 Kandidiasis, Komplikasi DM |
| OBT-024 | Parasetamol | rutin | tablet | K11 ISPA |
| OBT-025 | Sertralin | esensial | tablet | K12 Depresi Antenatal |
| OBT-026 | Ranitidin | rutin | tablet | K13 GERD |
| OBT-027 | Omeprazol | rutin | kapsul | K13 GERD |
| OBT-028 | Laktulosa | rutin | botol | K14 Konstipasi |
| OBT-029 | Spiramisin | esensial | tablet | K10 Toksoplasmosis (T1) |
| OBT-030 | Pirimetamin | esensial | tablet | K10 Toksoplasmosis (T2-T3) |

#### **Ringkasan Semua ENUM Values**

| Tabel | Kolom | Semua Nilai |
| ----- | ----- | ----- |
| master\_puskesmas | tipe | terpencil, sangat\_terpencil |
| master\_puskesmas | skor\_aksesibilitas | 1 (buruk), 2 (sedang), 3 (baik) |
| master\_puskesmas | aksesibilitas\_musim\_hujan | terputus, terganggu, normal |
| master\_obat | kategori | darurat, esensial, rutin |
| master\_obat | tipe | universal, tambahan |
| master\_obat | satuan | tablet, kapsul, vial, tube, botol |
| kb\_kondisi\_obat | trimester\_applicable | T1, T2, T3, T1,T2, T2,T3, T1,T2,T3 |
| kb\_kondisi\_obat | prioritas | 1 (utama), 2 (alternatif) |
| input\_diagnosis\_periode | sumber\_diagnosis | lab, klinis, rdt |
| input\_konteks\_periode | musim | hujan, kemarau |
| output\_prediksi\_stok | confidence\_level | high (\>0.8), medium (0.5-0.8), low (\<0.5) |
| output\_lplpo\_prediktif | prioritas | darurat, esensial, rutin |

