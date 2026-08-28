from PIL import Image
img = Image.open(r"C:\Users\Mc Marteen\Downloads\GPSXCamera_20260829_0037_IlocosRegion_16.043846_120.64401_17.jpg")

print("format:", img.format, "size:", img.size)
print("_getexif():", img._getexif())
print("getexif():", dict(img.getexif()))
try:
    print("GPS IFD:", dict(img.getexif().get_ifd(0x8825)))
except Exception as e:
    print("GPS IFD failed:", e)