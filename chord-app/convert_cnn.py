import tensorflow as tf
from tensorflow.keras import layers, models
from keras.models import load_model

# ===============================
# 1. Cargar modelo original
# ===============================
old_model = load_model("models/cnn_extractor.h5")

# ===============================
# 2. Crear modelo nuevo (channels_last)
# ===============================
def build_new_model():
    model = models.Sequential()
    reg = tf.keras.regularizers.L2(1e-3)

    model.add(layers.Conv2D(32, 3, activation='relu',
        input_shape=(105, 15, 1), padding='same',
        data_format='channels_last', kernel_regularizer=reg))
    model.add(layers.BatchNormalization())

    model.add(layers.Conv2D(32, 3, activation='relu',
        padding='same', data_format='channels_last', kernel_regularizer=reg))
    model.add(layers.BatchNormalization())

    model.add(layers.Conv2D(32, 3, activation='relu',
        padding='same', data_format='channels_last', kernel_regularizer=reg))
    model.add(layers.BatchNormalization())

    model.add(layers.Conv2D(32, 3, activation='relu',
        padding='same', data_format='channels_last', kernel_regularizer=reg))
    model.add(layers.BatchNormalization())

    model.add(layers.MaxPooling2D((2,1)))
    model.add(layers.Dropout(0.3))

    model.add(layers.Conv2D(64, 3, activation='relu',
        padding='valid', data_format='channels_last', kernel_regularizer=reg))
    model.add(layers.BatchNormalization())

    model.add(layers.Conv2D(64, 3, activation='relu',
        padding='valid', data_format='channels_last', kernel_regularizer=reg))
    model.add(layers.BatchNormalization())

    model.add(layers.MaxPooling2D((2,1)))
    model.add(layers.Dropout(0.3))

    model.add(layers.Conv2D(128, (12,9), activation='relu',
        padding='valid', data_format='channels_last', kernel_regularizer=reg))
    model.add(layers.BatchNormalization())
    model.add(layers.Dropout(0.3))

    # 👇 ESTA NO LA QUEREMOS PARA FEATURES
    model.add(layers.Conv2D(25, (1,1), activation='linear',
        padding='valid', data_format='channels_last', kernel_regularizer=reg))
    model.add(layers.BatchNormalization())

    model.add(layers.AveragePooling2D((13,3)))
    model.add(layers.Flatten())

    return model

new_model = build_new_model()

# ===============================
# 3. Copiar pesos
# ===============================
print("\n🔄 Copiando pesos...\n")

for i, layer in enumerate(old_model.layers):
    try:
        new_model.layers[i].set_weights(layer.get_weights())
        print(f"Layer {i} OK")
    except Exception as e:
        print(f"Layer {i} skipped")

# ===============================
# 4. Encontrar capa de 128 features
# ===============================
print("\n🔍 Buscando capa de 128 features...\n")

feature_layer_index = None

for i, layer in enumerate(new_model.layers):
    shape = layer.output_shape
    print(i, layer.name, shape)

    # buscamos capa con 128 canales
    if isinstance(shape, tuple) and len(shape) == 4:
        if shape[-1] == 128:
            feature_layer_index = i

# ===============================
# 5. Crear extractor FINAL
# ===============================
if feature_layer_index is None:
    raise Exception("❌ No se encontró capa de 128 features")

print(f"\n✅ Usando capa {feature_layer_index} como extractor\n")

extractor = tf.keras.Model(
    inputs=new_model.input,
    outputs=new_model.layers[feature_layer_index].output
)

# ===============================
# 6. Aplanar salida a (128,)
# ===============================
x = extractor.output
x = layers.GlobalAveragePooling2D()(x)  # 🔥 convierte a vector (128,)

extractor = tf.keras.Model(inputs=extractor.input, outputs=x)

# ===============================
# 7. Guardar modelo final
# ===============================
extractor.save("models/cnn_extractor_fixed.h5")

print("\n🎉 Modelo convertido correctamente")