import openwakeword
from openwakeword.model import Model

openwakeword.utils.download_models()

model = Model()
#model.add_keyword("alexa")  # eller spesifiser model_path hvis nødvendigls 