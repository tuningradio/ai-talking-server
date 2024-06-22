# ai-talking-server.py by Tuningradio & Microsoft Copilot 2024.06.19
# 無線機と連動できる音声chat server

# 使い方
# 1)事前にLM studio serverを起動しておく。modelは日本語学習したものを使う事。それと同じモデル名を下記ソースにも設定しておく。
# 2)事前にVOICEVOX coreを起動しておく。"C:\Program Files\VOICEVOX\vv-engine\run.exe" --host 127.0.0.1
# 3)COMポートのDTRで無線機のPTTコントロールをしたい場合は -c COM7 のように起動パラメーターで指定する。SignaLINKやVOXの場合は不要です。
# 4)起動したらオーディオ入力デバイスID番号と、同出力デバイスIDを指定する。
# 5)ctrl+cで終了する。
# 
# 動作説明：  
# 1)音声をgoogle recognizerに渡す。
# 2)帰ってきたテキストをLM studio serverに渡す。LM studio server側は日本語モデルであること。英語モデルに渡すと英語で返答してしまう。
# 3)LM studio serverの返答をVOICEVOXに渡す。
# 4)VOICEVOXから返ってきた音声データーをオーディオ出力デバイスにストリーミング再生する。
# 5)ストリーミング再生中、-c で指定されたCOMポートのDTRをONにする(=無線機は送信状態になる)。ストリーミング終了でDTRをOFFにする(=無線機は受信状態に戻る)。
#
# 使い方のコツ：
# あんまり送信時間が長いと怪しまれるので、LM studio serverの tokens to generate n_gpu_layers の値を20～50ぐらいにしておいたほうが良い。(50トークン ≒ 50文字)
# 
# 既知のバグ：
# バグというか・・・アルファベットを話されると、日本語モデルのくせに(笑)英語を返してくる。VOICEVOXがそれをアルファベット一文字ずつ読み始めて収拾がつかなくなる。
# そうなったらこのプログラムを強制終了して、布団かぶって寝るか再起動する。

import speech_recognition as sr
import pyaudio
import requests
import base64
import sys
import subprocess
import serial
import argparse
import json
from openai import OpenAI
from datetime import datetime, timezone, timedelta


# コマンドライン引数の解析
parser = argparse.ArgumentParser(description="ai-talking-server.py 1.0.0(W)")
parser.add_argument('-c', '--com', help='DTR制御をしたいCOMポート名')
args = parser.parse_args()

# 音声デバイスの一覧表示と選択
def select_audio_device(device_type):
    p = pyaudio.PyAudio()
    print(f"\n\nAvailable {device_type} devices:")
    for i in range(p.get_device_count()):
        device_info = p.get_device_info_by_index(i)
        if (device_type == 'input' and device_info['maxInputChannels'] > 0) or \
           (device_type == 'output' and device_info['maxOutputChannels'] > 0):
            print(i, device_info['name'])
    device = int(input(f"Please enter the number of the {device_type} device: "))
    return device

# 音声入力デバイスの選択
input_device_index = select_audio_device('input')

# 音声出力デバイスの選択
output_device_index = select_audio_device('output')

# COMポートの設定
com_port = args.com  # 起動パラメータでCOMポートを指定
if com_port:
    ser = serial.Serial(com_port)  # COMポートを開く
    ser.setDTR(False)  # DTRを強制OFFにする（初期化）
else:
    print("COMポートが指定されなかったので、DTR制御をしません。")

# 音声認識オブジェクトの作成
r = sr.Recognizer()

# サンプリング周波数の設定
r.sample_rate = 15000

try:
    # マイクから音声を取得し、Ctrl+Cが押されるまでループ
    while True:
        with sr.Microphone(device_index=input_device_index, sample_rate=r.sample_rate) as source:
            print(f"{datetime.now(timezone(timedelta(hours=+9))).isoformat()} 音声を入力してください:")
            audio = r.listen(source)

            try:
                # Googleの音声認識APIを使用して音声をテキストに変換
                text = r.recognize_google(audio, language="ja-JP")
                print(f"{datetime.now(timezone(timedelta(hours=+9))).isoformat()} テキスト: ", text)

                # テキストをprompt.txtに保存
                try:
                    with open('prompt.txt', 'w') as f:
                        f.write(text)
                except IOError as e:
                    print(f"{datetime.now(timezone(timedelta(hours=+9))).isoformat()} ファイルオープンエラー: {e}")

                ##########
                # LM Studioにprompt.txtを渡す

                # prompt.txtファイルを開く
                with open('prompt.txt', 'r') as file:
                    # ファイルの内容を読み込む
                    user_input = file.read().strip()

                # Point to the local server
                client = OpenAI(base_url="http://192.168.1.103:1234/v1", api_key="lm-studio")

                completion = client.chat.completions.create(
                  model="mradermacher/Llama-3-8b-Cosmopedia-japanese-GGUF",
                  messages=[
                    {"role": "system", "content": "あなたはAIアシスタントです。あなたはバーチャル局長です。あなたはいつでも日本語で回答します。"},
                    {"role": "user", "content": user_input}
                      ],
                  temperature=0.1,
                )

                # contentの部分だけを表示
                print(completion.choices[0].message.content)


                ################
                # VOICEVOXにテキストを渡して話させる

                def generate_and_play_audio_from_text(text, speaker=1, SpeedScale=5):
                    host = 'localhost'
                    port = 50021

                    params = {
                        'text': text,
                        'speaker': speaker,
                    }

                    response1 = requests.post(f'http://{host}:{port}/audio_query', params=params)

                    if response1.status_code != 200:
                        print("VOICEVOXエンジンが起動していない可能性があります。")
                        sys.exit(1)

                    headers = {'Content-Type': 'application/json'}
                    response2 = requests.post(
                        f'http://{host}:{port}/synthesis',
                        headers=headers,
                        params=params,
                        data=json.dumps(response1.json())
                    )

                    if response2.status_code == 200:
                        # 音声データをストリーミング再生する
                        audio_data = response2.content

                        # pyaudioを使って音声データを再生
                        p = pyaudio.PyAudio()
        
                        # ストリームの設定
                        stream = p.open(format=pyaudio.paInt16,
                                        channels=1,
                                        rate=24000,
                                        output=True,
                                        output_device_index=output_device_index)
                        if com_port:
                            ser.setDTR(True)
                        # バッファサイズを適切に設定して音声データを分割再生
                        buffer_size = 1024
                        for i in range(0, len(audio_data), buffer_size):
                            stream.write(audio_data[i:i+buffer_size])

                        # ストリームを閉じる
                        stream.stop_stream()
                        stream.close()
                        p.terminate()
                        if com_port:
                            ser.setDTR(False)
                    else:
                        print("音声の生成に失敗しました。")
                        sys.exit(1)

                if __name__ == '__main__':
                    # ここで、completion.choices[0].message.contentをtextとして指定します。
                    text = completion.choices[0].message.content
                    generate_and_play_audio_from_text(text, speaker=53, SpeedScale=9)

            except sr.UnknownValueError:
                print(f"{datetime.now(timezone(timedelta(hours=+9))).isoformat()} Google音声認識が音声を理解できませんでした")
            except sr.RequestError as e:
                print(f"{datetime.now(timezone(timedelta(hours=+9))).isoformat()} Google音声認識サービスから結果を要求できませんでした; {0}".format(e))

except KeyboardInterrupt:
    # Ctrl+Cが押されたときの処理
    print(f"{datetime.now(timezone(timedelta(hours=+9))).isoformat()} プログラムを終了します...")
    if com_port:
        ser.setDTR(False)  # DTRをOFFにする
        ser.close()  # COMポートを閉じる

