from foundry_local_sdk import Configuration, FoundryLocalManager


alias = "qwen3-0.6b"

# 1. Yapılandırmayı oluştur ve singleton'ı başlat
config = Configuration(app_name="microsoft_internship_project")
FoundryLocalManager.initialize(config)
manager = FoundryLocalManager.instance

# 2. Modeli katalogdan al ve indir/yükle
model = manager.catalog.get_model(alias)
model.download(lambda p: print(f"\rİndiriliyor: {p:.2f}%", end="", flush=True))
print()
model.load()
print("Model yüklendi.")

# 3. OpenAI uyumlu chat client
client = model.get_chat_client()

def main():
    response = client.complete_chat([
        {"role": "user", "content": "Why is the sky blue?"}
    ])
    print(response.choices[0].message.content)

if __name__ == "__main__":
    main()