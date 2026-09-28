# Kafka ve Grafana Tabanlı Kargo Takip Sistemi (Cargo Tracking System)

Bu proje; **Flask REST API**, **SQLite**, **Apache Kafka**, **Kafka Consumer**, **Prometheus** ve **Grafana** teknolojilerini bir araya getiren, uçtan uca mikroservis ve event-driven (olay güdümlü) mimariye sahip profesyonel bir kargo takip ve izleme sistemidir.

---

## 1. Proje Mimarisi ve Akışı

Sistem mimarisi olay güdümlü (Event-Driven) ve gerçek zamanlı izlenebilirlik (Observability) prensiplerine dayanmaktadır:

```text
Client (Postman / cURL / Frontend)
           │
           ▼
    Flask REST API (:5000)
    ├── SQLite Veritabanı (cargo.db)
    └── Kafka Producer
           │
           ▼ (cargo-events topic)
    Kafka Consumer
           │
           ▼
  Prometheus Metrikleri (:9090) ───► Flask /metrics
           │
           ▼
   Grafana Dashboard (:3000)
```

### Olay Akış Döngüsü:
1. **İstemci (Client)**, Flask REST API'ye HTTP isteği (POST, GET, PUT, DELETE) gönderir.
2. **Flask REST API**, veriyi doğrular, SQLite veritabanına kaydeder/günceller ve Prometheus metriklerini artırır.
3. Aynı anda **Kafka Producer**, `cargo-events` topic'ine JSON formatında durum olayını (`cargo.created`, `cargo.status_changed`, `cargo.delivered`, vb.) fırlatır.
4. **Kafka Consumer**, `cargo-events` topic'ini gerçek zamanlı dinler, gelen mesajları işler ve terminalde teslimat/durum loglarını gösterir.
5. **Prometheus**, periyodik olarak Flask API'nin `/metrics` endpoint'ini tarayarak metrikleri toplar.
6. **Grafana**, Prometheus veri kaynağını kullanarak oluşturulan metrikleri **"KARGO TAKİP SİSTEMİ"** dashboard'unda anlık olarak görselleştirir.

---

## 2. Kullanılan Teknolojiler

* **Backend / API:** Python 3.11 / Flask 3.0.2
* **Veritabanı:** SQLite 3 (Kalıcı disk depolama)
* **Mesaj Kuyruğu:** Apache Kafka 7.5.0 & Zookeeper
* **Metrik & Monitoring:** Prometheus 2.50.0 (`prometheus-client`)
* **Görselleştirme & Dashboard:** Grafana 10.3.3 (Otomatik Provisioning ile hazır dashboard)
* **Konteynerleştirme:** Docker & Docker Compose
* **Test Çatısı:** PyTest 8.0.0

---

## 3. Klasör Yapısı

```text
cargo-tracking/
│
├── app/
│   ├── __init__.py          # Flask App Factory ve servis başlatıcı
│   ├── routes.py            # REST API rotaları (CRUD ve durum geçişleri)
│   ├── models.py            # SQLite veritabanı CRUD fonksiyonları ve iş mantığı
│   ├── kafka_producer.py    # Kafka Producer wrapper ve olay tetikleyicileri
│   └── metrics.py           # Prometheus metrik tanımları ve middleware
│
├── consumer/
│   └── consumer.py          # Kafka Consumer (cargo-events dinleyicisi)
│
├── tests/
│   └── test_cargo.py        # PyTest unit ve entegrasyon testleri
│
├── prometheus/
│   └── prometheus.yml       # Prometheus scraping yapılandırması
│
├── grafana/
│   └── provisioning/
│       ├── datasources/
│       │   └── datasource.yml       # Otomatik Prometheus veri kaynağı tanımı
│       └── dashboards/
│           ├── dashboard.yml        # Otomatik dashboard yükleyici yapılandırması
│           └── cargo_dashboard.json # Kargo Takip Sistemi Dashboard JSON şablonu
│
├── requirements.txt         # Python bağımlılıkları
├── config.py                # Merkezi konfigürasyon ve ortam değişkenleri
├── run.py                   # API çalıştırma giriş noktası
├── Dockerfile               # Konteyner imajı oluşturma dosyası
├── docker-compose.yml       # Tüm servisleri ayağa kaldıran Compose dosyası
├── README.md                # Proje dokümantasyonu ve kullanım kılavuzu
└── WHITEPAPER.md            # Teknik rapor ve sistem analiz dokümanı
```

---

## 4. Kurulum ve Çalıştırma

### A) Docker Compose ile Çalıştırma (Önerilen)

Tüm altyapıyı (Flask, SQLite, Kafka, Consumer, Prometheus, Grafana) tek komutla başlatmak için:

```bash
docker compose up -d --build
```

Servislerin durumunu kontrol etmek için:

```bash
docker compose ps
```

Konteyner loglarını izlemek için:

```bash
# Consumer loglarını canlı izleme (Kargo teslimat bildirimleri burada akar)
docker compose logs -f consumer

# Flask API loglarını izleme
docker compose logs -f flask
```

Sistemi durdurmak için:

```bash
docker compose down
```

---

### B) Yerel Geliştirme Ortamında (Local Virtualenv) Çalıştırma

1. **Sanal Ortam Oluşturma ve Aktifleştirme:**
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. **Gereksinimlerin Yüklenmesi:**
   ```bash
   pip install -r requirements.txt
   ```

3. **API'yi Başlatma:**
   ```bash
   python run.py
   ```
   API `http://localhost:5000` adresinde çalışacaktır.

4. **Consumer'ı Başlatma:**
   ```bash
   python consumer/consumer.py
   ```

---

## 5. REST API Endpointleri ve Örnek İstekler

### Kargo Durumları (Lifecycle States):
* `CREATED`: Kargo kaydı oluşturuldu.
* `SHIPPED`: Kargoya verildi.
* `IN_TRANSIT`: Dağıtım merkezinde / Yolda.
* `OUT_FOR_DELIVERY`: Kurye dağıtımda.
* `DELIVERED`: Teslim edildi (Son Durum - değiştirilemez).
* `CANCELLED`: İptal edildi (Son Durum - değiştirilemez).

---

### 1. Kargo Oluşturma (`POST /cargo`)
* **Endpoint:** `POST http://localhost:5000/cargo`
* **Request Body:**
```json
{
  "tracking_number": "KRG-1001",
  "sender": "Ahmet Yılmaz",
  "receiver": "Mehmet Demir"
}
```
* **Response (201 Created):**
```json
{
  "id": 1,
  "tracking_number": "KRG-1001",
  "sender": "Ahmet Yılmaz",
  "receiver": "Mehmet Demir",
  "status": "CREATED",
  "created_at": "2026-09-28 13:30:00"
}
```

---

### 2. Kargo Sorgulama (`GET /cargo/<id>`)
* **Endpoint:** `GET http://localhost:5000/cargo/1`
* **Response (200 OK):**
```json
{
  "id": 1,
  "tracking_number": "KRG-1001",
  "sender": "Ahmet Yılmaz",
  "receiver": "Mehmet Demir",
  "status": "CREATED",
  "created_at": "2026-09-28 13:30:00"
}
```
* **Kargo bulunamazsa (404 Not Found):**
```json
{
  "error": "Cargo not found"
}
```

---

### 3. Tüm Kargoları Listeleme (`GET /cargo`)
* **Endpoint:** `GET http://localhost:5000/cargo`
* **Response (200 OK):**
```json
[
  {
    "id": 1,
    "tracking_number": "KRG-1001",
    "sender": "Ahmet Yılmaz",
    "receiver": "Mehmet Demir",
    "status": "CREATED",
    "created_at": "2026-09-28 13:30:00"
  }
]
```

---

### 4. Kargo Durumu Güncelleme (`PUT /cargo/<id>/status`)
* **Endpoint:** `PUT http://localhost:5000/cargo/1/status`
* **Request Body:**
```json
{
  "status": "IN_TRANSIT"
}
```
* **Response (200 OK):**
```json
{
  "id": 1,
  "tracking_number": "KRG-1001",
  "sender": "Ahmet Yılmaz",
  "receiver": "Mehmet Demir",
  "status": "IN_TRANSIT",
  "created_at": "2026-09-28 13:30:00"
}
```
* **Kural İhlali Durumunda (Örn: DELIVERED kargoyu geri alma - 400 Bad Request):**
```json
{
  "error": "Delivered cargo cannot change status"
}
```

---

### 5. Kargo Silme (`DELETE /cargo/<id>`)
* **Endpoint:** `DELETE http://localhost:5000/cargo/1`
* **Response (200 OK):**
```json
{
  "message": "Cargo deleted successfully"
}
```

---

## 6. Kafka Olayları (Events) ve Şemalar

Topic Adı: `cargo-events`

1. **Kargo Oluşturulduğunda:**
```json
{
  "event": "cargo.created",
  "cargo_id": 1,
  "tracking_number": "KRG-1001"
}
```

2. **Kargo Durumu Değiştiğinde:**
```json
{
  "event": "cargo.status_changed",
  "cargo_id": 1,
  "status": "IN_TRANSIT"
}
```

3. **Kargo Teslim Edildiğinde:**
```json
{
  "event": "cargo.delivered",
  "cargo_id": 1
}
```

4. **Kargo İptal Edildiğinde:**
```json
{
  "event": "cargo.cancelled",
  "cargo_id": 1
}
```

---

## 7. Prometheus Metrikleri ve Grafana Dashboard

### Prometheus Metrikleri (`http://localhost:5000/metrics`)
* `cargo_created_total`: Toplam oluşturulan kargo adedi (Counter).
* `cargo_delivered_total`: Toplam teslim edilen kargo adedi (Counter).
* `cargo_cancelled_total`: Toplam iptal edilen kargo adedi (Counter).
* `cargo_status_changed_total`: Toplam kargo durum geçişi sayısı (Counter).
* `api_request_total`: HTTP isteklerinin toplam sayısı (`method`, `endpoint`, `status_code` etiketleri ile).
* `api_request_duration_seconds`: API yanıt süreleri (Histogram).

### Grafana Dashboard (`http://localhost:3000`)
* **Giriş Bilgileri:** Kullanıcı: `admin` | Şifre: `admin`
* **Dashboard Başlığı:** `KARGO TAKİP SİSTEMİ`
* **Paneller:**
  1. **Toplam Kargo** (Stat panel)
  2. **Teslim Edilen Kargo** (Stat panel)
  3. **İptal Edilen Kargo** (Stat panel)
  4. **Dakikadaki Kargo İşlemleri** (Time series graph)
  5. **API Response Time** (Time series graph)

---

## 8. Unit Testler (PyTest)

Tüm iş mantığı, doğrulama kuralları, veritabanı CRUD işlemleri ve HTTP uç noktaları PyTest ile test edilir.

Testleri çalıştırmak için:
```bash
pytest
# veya detaylı çıktı için:
pytest tests/ -v
```

Test Kapsamı:
* Geçerli verilerle kargo oluşturma (`201 Created`)
* Boş tracking number veya eksik alan doğrulama kontrolü (`400 Bad Request`)
* Mükerrer tracking number kontrolü (`400 Bad Request`)
* Olmayan kargo sorgulama kontrolü (`404 Not Found`)
* Kargo detay sorgulama ve toplu listeleme (`200 OK`)
* Durum geçişlerinin doğruluğu (`200 OK`)
* Geçersiz durum değeri koruması (`400 Bad Request`)
* DELIVERED kargonun durumunun değiştirilemezlik kuralı (`400 Bad Request`)
* CANCELLED kargonun durumunun değiştirilemezlik kuralı (`400 Bad Request`)
* Kargo silme ve silinen kargonun 404 dönmesi
* Prometheus `/metrics` endpoint testi
* Doğrudan model CRUD fonksiyon testleri
