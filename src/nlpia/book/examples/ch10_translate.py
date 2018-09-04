import os
import numpy as np
from nlpia.constants import BIGDATA_PATH
lang = 'deu'  # see nlpia.loaders.ANKI_LANGUAGES for more options besides German

checkpoint_dir = os.path.join(BIGDATA_PATH, 'checkpoints')
encoder_input_path = os.path.join(
    checkpoint_dir,
    'nlpia-ch10-translate-input-{}.npy'.format(lang))
decoder_input_path = os.path.join(
    checkpoint_dir,
    'nlpia-ch10-translate-decoder-input-{}.npy'.format(lang))
decoder_target_path = os.path.join(
    checkpoint_dir,
    'nlpia-ch10-translate-target-{}.npy'.format('eng'))
data_paths = tuple(((v + '_path', v + '_data') for v in 
                    'encoder_input decoder_input decoder_target'.split()))


def generate_training_data(lang):
    from nlpia.loaders import get_data
    from tqdm import tqdm

    df = get_data('deu')
    input_texts, target_texts = [], []  # <1>
    input_vocabulary = set()  # <3>
    output_vocabulary = set()
    start_token, stop_token = '\t\n'  # <2>
    n = len(df)

    for input_text, target_text in tqdm(zip(df.eng, df.deu), total=n):
        target_text = start_token + target_text \
            + stop_token  # <7>
        input_texts.append(input_text)
        target_texts.append(target_text)
        for char in input_text:  # <8>
            if char not in input_vocabulary:
                input_vocabulary.add(char)
        for char in target_text:
            if char not in output_vocabulary:
                output_vocabulary.add(char)

    input_vocabulary = sorted(input_vocabulary)  # <1>
    output_vocabulary = sorted(output_vocabulary)

    input_vocab_size = len(input_vocabulary)  # <2>
    output_vocab_size = len(output_vocabulary)
    max_encoder_seq_length = max(
        [len(txt) for txt in input_texts])  # <3>
    max_decoder_seq_length = max(
        [len(txt) for txt in target_texts])

    input_token_index = dict([(char, i) for i, char in
                              enumerate(input_vocabulary)])  # <4>
    target_token_index = dict(
        [(char, i) for i, char in enumerate(output_vocabulary)])
    reverse_input_char_index = dict((i, c) for (c, i) in
                                    input_token_index.items())  # <5>
    reverse_target_char_index = dict((i, c) for (c, i) in
                                     target_token_index.items())

    import numpy as np  # <1>  # noqa

    encoder_input_data = np.zeros((n, max_encoder_seq_length, input_vocab_size),
                                  dtype='float32')  # <2>
    decoder_input_data = np.zeros((n, max_decoder_seq_length, output_vocab_size),
                                  dtype='float32')
    decoder_target_data = np.zeros((n, max_decoder_seq_length, output_vocab_size),
                                   dtype='float32')
    for i, (input_text, target_text) in enumerate(tqdm(
            zip(input_texts, target_texts), total=len(target_texts))):  # <3>
        for t, char in enumerate(input_text):  # <4>
            encoder_input_data[
                i, t, input_token_index[char]] = 1.  # <5>
        for t, char in enumerate(target_text):  # <6>
            decoder_input_data[
                i, t, target_token_index[char]] = 1.
            if t > 0:
                decoder_target_data[i, t - 1, target_token_index[char]] = 1

    for (p, v) in data_paths:
        np.save(globals()[p], globals()[v], allow_pickle=False)

    return encoder_input_data, decoder_input_data, decoder_target_data


def fit(
        encoder_input_data=None,
        decoder_input_data=None,
        decoder_target_data=None,
        trainset_size=1000
        ):

    input_vocab_size = encoder_input_data.shape[2]
    output_vocab_size = decoder_target_data.shape[2]

    # import pandas as pd  # noqa
    # encoder_input_data = pd.DataFrame(encoder_input_data)

    from keras.models import Model  # noqa
    from keras.layers import Input, LSTM, Dense  # noqa

    batch_size = 64    # <1>
    epochs = 100       # <2>
    num_neurons = 256  # <3>

    encoder_inputs = Input(shape=(None, input_vocab_size))
    encoder = LSTM(num_neurons, return_state=True)
    encoder_outputs, state_h, state_c = encoder(encoder_inputs)
    encoder_states = [state_h, state_c]

    decoder_inputs = Input(shape=(None, output_vocab_size))
    decoder_lstm = LSTM(num_neurons, return_sequences=True,
                        return_state=True)
    decoder_outputs, _, _ = decoder_lstm(decoder_inputs,
                                         initial_state=encoder_states)
    decoder_dense = Dense(output_vocab_size, activation='softmax')
    decoder_outputs = decoder_dense(decoder_outputs)
    model = Model([encoder_inputs, decoder_inputs], decoder_outputs)

    model.compile(optimizer='rmsprop', loss='categorical_crossentropy',
                  metrics=['acc'])

    import os  # noqa
    from keras.callbacks import ModelCheckpoint  # noqa
    from nlpia.constants import BIGDATA_PATH  # noqa
    checkpoint_path = os.path.join(BIGDATA_PATH, 'checkpoints')
    checkpoint_path = os.path.join(checkpoint_path, 'nlpia-seq2seq-translation-weights.{epoch:02d}-{val_loss:.2f}.hdf5')

    checkpoint_callback = ModelCheckpoint(checkpoint_path,
                                          monitor='val_loss', verbose=0, save_best_only=False, mode='auto')
    model.fit([encoder_input_data, decoder_input_data],
              decoder_target_data,
              callbacks=[checkpoint_callback],
              batch_size=batch_size, epochs=epochs, validation_split=0.1)  # <4>

    return model


if __name__ == '__main__':
    if all([os.path.isfile(locals()[p]) for (p, data) in data_paths]):
        encoder_input_data = np.load(encoder_input_path)
        decoder_input_data = np.load(decoder_input_path)
        decoder_target_data = np.load(decoder_target_path)
    else:
        encoder_input_data, decoder_input_data, decoder_target_data = generate_training_data(lang)
    kwargs = dict([(p, locals()[v]) for (p, v) in data_paths])
    fit(**kwargs)

