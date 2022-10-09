import requests
from pathlib import Path
def get_QRcode():
    url = "https://uis.nwpu.edu.cn/cas/qr/qrcode?r=166529844470216"
    response = requests.get(url)
    img = response.content
    with open(Path(__file__).parent / "QRcode.png", 'wb') as f:
        f.write(img)

get_QRcode()