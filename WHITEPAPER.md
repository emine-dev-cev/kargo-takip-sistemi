# KAFKA VE GRAFANA TABANLI KARGO TAKİP SİSTEMİ TEKNİK RAPORU (WHITEPAPER)

---

## 1. Projenin Amacı

Günümüz modern lojistik ve tedarik zinciri ekosistemlerinde kargo takip operasyonları; yüksek veri hacmi, anlık durum güncellemeleri, güvenilirlik ve sistem sağlığının kesintisiz izlenmesini gerektirir. 

Bu projenin temel amacı; mikroservis odaklı, olay güdümlü (Event-Driven Architecture) ve tam gözlemlenebilir (Observability) bir **Kargo Takip Sistemi** inşa etmektir. Sistem; kargo gönderilerinin kabul edilmesinden nihai alıcıya teslimine kadar geçen tüm yaşam döngüsünü (Lifecycle) hatasız yönetirken, durum değişikliklerini anlık mesaj kuyruğu (Apache Kafka) üzerinden yaymakta ve tüm operasyonel metrikleri Prometheus & Grafana aracılığıyla gerçek zamanlı izlenebilir kılmaktadır.

---

## 2. Sistem Mimarisi

Sistem, loosely-coupled (gevşek bağlı) ve yatayda ölçeklenebilir 6 ana bileşenden oluşmaktadır:

```text
                  +-------------------------+
                  |         Client          |
                  | (cURL / Postman / App)  |
                  +------------+------------+
                               |
                        [HTTP REST API]
                               |
                               v
                  +-------------------------+
                  |     Flask REST API      |
                  |  (Port: 5000 / Python)  |
                  +----+---------------+----+
                       |               |
              [Disk I/O / SQL]   [Async Events]
                       |               |
                       v               v
               +---------------+ +-------------------+
               |  SQLite DB    | |   Kafka Producer  |
               |  (cargo.db)   | +---------+---------+
               +---------------+           |
                                   [cargo-events]
                                           |
                                           v
                                 +-------------------+
                                 |  Apache Kafka     |
                                 |  Broker (:9092)   |
                                 +---------+---------+
                                           |
                                   [Consumer Stream]
                                           |
                                           v
                                 +-------------------+
                                 |  Kafka Consumer   |
                                 | (consumer.py log) |
                                 +-------------------+

[Observability & Monitoring Pipeline]
Flask (/metrics) ───(Pull: 5s)───► Prometheus (:9090) ───(Query)───► Grafana (:3000)
```

### Mimari Bileşenlerin Rolü:
1. **İstemci (Client):** Kargo oluşturma, durum güncelleme, silme ve sorgulama isteklerini HTTP üzerinden API'ye iletir.
2. **Flask REST API:** İş kurallarını denetler, veritabanı işlemlerini koordine eder, Prometheus metriklerini sayar ve Kafka olaylarını fırlatır.
3. **SQLite Veritabanı:** Kargo verilerini ACID prensiplerine uygun olarak kalıcı diskte saklar.
4. **Apache Kafka:** Servisler arası asenkron olay dağıtımını garantiler.
5. **Kafka Consumer:** `cargo-events` topic'indeki kargo oluşturma, durum değişimi ve teslimat bildirimlerini dinleyerek işler.
6. **Prometheus & Grafana:** Sistem performansını (yanıt süreleri) ve iş metriklerini (teslimat, iptal sayıları) merkezi panelde görselleştirir.

---

## 3. Flask REST API

Flask REST API, REST standartlarına ve HTTP durum kodlarına tam uyumlu olarak tasarlanmıştır.

### Uç Noktalar (Endpoints):
* `POST /cargo`: Yeni kargo gönderisi kaydeder.
  * *İstek:* `{"tracking_number": "KRG-1001", "sender": "Ahmet", "receiver": "Mehmet"}`
  * *Başarılı Yanıt (201 Created):* `{ "id": 1, "tracking_number": "KRG-1001", "status": "CREATED", ... }`
  * *Doğrulama Hatası (400 Bad Request):* Eksik alanlar veya mükerrer takip numarası girilirse açıklayıcı JSON hatası döner.
* `GET /cargo/<id>`: Belirtilen kargo detayını döner (200 OK veya 404 Not Found).
* `GET /cargo`: Sistemdeki tüm kayıtlı kargoları liste halinde döner (200 OK).
* `PUT /cargo/<id>/status`: Kargo durumunu günceller.
  * *İstek:* `{"status": "IN_TRANSIT"}`
  * *İş Kuralı:* `DELIVERED` ve `CANCELLED` statüsündeki kargoların durumu değiştirilemez (400 Bad Request).
* `DELETE /cargo/<id>`: Kargo kaydını sistemden siler (200 OK veya 404 Not Found).
* `GET /metrics`: Prometheus metriklerini `text/plain; version=0.0.4` formatında sunar.

---

## 4. SQLite Veritabanı

Veriler gerçek ve kalıcı bir SQLite veritabanı dosyasında saklanır (`cargo.db` / Docker hacminde `/app/data/cargo.db`).

### Tablo Şeması (`cargo`):
```sql
CREATE TABLE IF NOT EXISTS cargo (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tracking_number TEXT NOT NULL UNIQUE,
    sender TEXT NOT NULL,
    receiver TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'CREATED',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Kargo Yaşam Döngüsü ve Durum Geçişleri:
* `CREATED` (Kayıt Açıldı)
* `SHIPPED` (Kargoya Verildi)
* `IN_TRANSIT` (Transfer Merkezinde / Yolda)
* `OUT_FOR_DELIVERY` (Kurye Dağıtımda)
* `DELIVERED` (Teslim Edildi - Terminal Durum)
* `CANCELLED` (İptal Edildi - Terminal Durum)

Veritabanı işlemleri `app/models.py` modülü altında kapsüllenmiş olup, SQL injection risklerine karşı parametrik sorgular (`?`) kullanılmıştır.

---

## 5. Unit Testler

Sistemin kararlılığı ve iş kurallarının doğrulanması için **PyTest** test çatısı kullanılmıştır.

### Test Edilen Başlıca Senaryolar:
1. `test_create_cargo_success`: Geçerli bilgilerle kargo oluşturulması ve 201 kodu doğrulanması.
2. `test_create_cargo_empty_tracking_number`: Takip numarası boş bırakıldığında 400 hatasının üretilmesi.
3. `test_create_cargo_missing_fields`: Gönderici/alıcı eksik bırakıldığında 400 hatasının üretilmesi.
4. `test_create_cargo_duplicate_tracking_number`: Aynı takip numarası ile ikinci kayıt oluşturulmasının engellenmesi.
5. `test_get_cargo_not_found`: Olmayan bir kargo sorgulandığında 404 dönmesi.
6. `test_get_cargo_by_id_success`: Var olan kargonun id üzerinden başarıyla sorgulanması.
7. `test_get_all_cargos`: Tüm kargoların dizi olarak listelenmesi.
8. `test_update_cargo_status_success`: Durumun `IN_TRANSIT`, `OUT_FOR_DELIVERY` vb. geçişlerinin sağlanması.
9. `test_update_cargo_invalid_status`: Tanımsız bir durum gönderildiğinde 400 hatası dönmesi.
10. `test_update_status_delivered_cannot_revert`: `DELIVERED` durumundaki kargonun tekrar değiştirilememesi kuralının doğrulanması.
11. `test_update_status_cancelled_cannot_change`: `CANCELLED` durumundaki kargonun değiştirilememesi.
12. `test_delete_cargo_success`: Kargonun veritabanından başarıyla silinmesi.
13. `test_delete_cargo_not_found_after_deletion`: Silinen kargonun tekrar sorgulandığında 404 dönmesi.
14. `test_prometheus_metrics_endpoint`: `/metrics` ucunun metrikleri doğru formatta ürettiğinin doğrulanması.
15. `test_direct_model_functions`: Model fonksiyonlarının doğrudan izole CRUD testleri.

---

## 6. Kafka Producer

Flask API içerisine entegre edilen `app/kafka_producer.py`, durum değişikliklerini anlık olarak Kafka kuyruğuna aktarır.

* **Kafka Topic:** `cargo-events`
* **Serileştirme:** JSON (`utf-8` encoded)

### Olay Tipleri ve Veri Yapıları:
1. **Oluşturma Olayı (`cargo.created`):**
   ```json
   { "event": "cargo.created", "cargo_id": 1, "tracking_number": "KRG-1001" }
   ```
2. **Durum Değişikliği Olayı (`cargo.status_changed`):**
   ```json
   { "event": "cargo.status_changed", "cargo_id": 1, "status": "IN_TRANSIT" }
   ```
3. **Teslimat Olayı (`cargo.delivered`):**
   ```json
   { "event": "cargo.delivered", "cargo_id": 1 }
   ```
4. **İptal Olayı (`cargo.cancelled`):**
   ```json
   { "event": "cargo.cancelled", "cargo_id": 1 }
   ```

Kafka Producer, asenkron `send` ve `flush` operasyonları ile ağ gecikmelerini minimize eder; bağlantı kopukluklarında otomatik yeniden deneme (retry) mekanizmasına sahiptir.

---

## 7. Kafka Consumer

`consumer/consumer.py` servisi, `cargo-events` topic'ini sürekli dinleyen bağımsız bir arka plan worker'ıdır.

* **Tüketici Grubu (Group ID):** `cargo-consumer-group`
* **İşleme Mantığı:** Gelen olayları deserialize ederek tipine göre ayrıştırır.
* **Teslimat Bildirimi:** Kargo teslim edildiğinde konsola doğrudan istenen standartta çıktı üretir:
  ```text
  Cargo 15 delivered.
  ```
* **Dirençlilik:** Kafka broker henüz ayağa kalkmamışsa çökmek yerine periyodik olarak bağlantıyı yeniden dener (Exponential backoff & retry loop).

---

## 8. Prometheus Metrikleri

API istekleri ve kargo operasyonları için `prometheus-client` kütüphanesi ile özel metrikler oluşturulmuştur:

| Metrik Adı | Tip | Açıklama |
| :--- | :--- | :--- |
| `cargo_created_total` | Counter | Toplam oluşturulan kargo sayısı |
| `cargo_delivered_total` | Counter | Toplam teslim edilen kargo sayısı |
| `cargo_cancelled_total` | Counter | Toplam iptal edilen kargo sayısı |
| `cargo_status_changed_total` | Counter | Toplam kargo durum geçişi sayısı |
| `api_request_total` | Counter | API HTTP istek sayısı (etiketler: `method`, `endpoint`, `status_code`) |
| `api_request_duration_seconds` | Histogram | API isteklerinin yanıt süresi dağılımı (saniye) |

Flask `before_request` ve `after_request` kancalarıyla tüm API trafiği otomatik olarak ölçümlenir.

---

## 9. Grafana Dashboard

Grafana; `grafana/provisioning/` dizini altındaki otomatik yapılandırma (Provisioning) dosyaları sayesinde hiçbir manuel ayar gerektirmeden çalışmaya hazır gelir.

* **Dashboard Başlığı:** `KARGO TAKİP SİSTEMİ`
* **Veri Kaynağı:** Prometheus (`http://prometheus:9090`)

### Dashboard Panelleri ve PromQL Sorguları:
1. **Toplam Kargo (Stat Panel):** `cargo_created_total`
2. **Teslim Edilen Kargo (Stat Panel):** `cargo_delivered_total`
3. **İptal Edilen Kargo (Stat Panel):** `cargo_cancelled_total`
4. **Dakikadaki Kargo İşlemleri (Time Series Panel):** `rate(cargo_status_changed_total[1m]) * 60` ve `rate(cargo_created_total[1m]) * 60`
5. **API Response Time (Time Series Panel):** `sum(rate(api_request_duration_seconds_sum[1m])) / sum(rate(api_request_duration_seconds_count[1m]))`

---

## 10. Docker Compose Mimarisi

Tüm sistem `docker compose up -d` komutu ile tek hamlede ayağa kalkar.

### Servisler ve Bağımlılıklar:
1. `zookeeper`: Kafka koordinasyon servisi (Healthcheck ile doğrulanır).
2. `kafka`: Mesaj brokerı (Zookeeper'a bağımlıdır).
3. `flask`: Python Flask REST API (Kafka healthcheck'ini bekler, SQLite hacmi barındırır).
4. `consumer`: Python Kafka Consumer (Kafka broker'ına bağımlıdır).
5. `prometheus`: Flask `/metrics` ucunu her 5 saniyede bir tarar.
6. `grafana`: Prometheus'u veri kaynağı olarak tüketir ve dashboard'u açar.

Tüm servisler `cargo_network` adlı izole bir köprü ağında birbirleriyle haberleşir.

---

## 11. Test Senaryosu ve Doğrulama

Ödevde belirtilen kapsamlı test senaryosu simüle edilmiştir:

1. **20 Adet Kargo Oluşturuldu:** `POST /cargo` ile `KRG-1001` - `KRG-1020` arası kargolar eklendi. (`cargo_created_total` = 20)
2. **10 Kargonun Durumu `IN_TRANSIT` Yapıldı:** `PUT /cargo/<id>/status` ile statü güncellendi.
3. **5 Kargo `DELIVERED` Durumuna Getirildi:** Teslimat olayları üretildi (`cargo_delivered_total` = 5). Consumer konsolunda teslimat mesajları basıldı.
4. **2 Kargo `CANCELLED` Yapıldı:** İptal statüsüne geçirildi (`cargo_cancelled_total` = 2).
5. **Geçersiz Durum Geçişleri Test Edildi:** `DELIVERED` ve `CANCELLED` kargoların durumlarının değiştirilemeyeceği doğrulandı.
6. **PyTest:** 15 testin tamamı `PASSED` oldu.
7. **Prometheus & Grafana:** Metriklerin başarıyla grafiğe döküldüğü ve anlık güncellendiği doğrulandı.

---

## 12. Sonuç

Geliştirilen **Kafka ve Grafana Tabanlı Kargo Takip Sistemi**; yüksek performanslı bir REST API, güvenilir bir veritabanı katmanı, asenkron ve dağıtık bir mesaj kuyruğu altyapısı ile modern gözlemlenebilirlik (Prometheus & Grafana) araçlarını kusursuz bir şekilde entegre etmiştir. Kod tabanı temiz, modüler, anlaşılır ve tüm gereksinimleri %100 eksiksiz karşılayan profesyonel bir kurumsal mimari sunmaktadır.
