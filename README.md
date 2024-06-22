# ai-talking-server.py by Tuningradio & Microsoft Copilot 2024.06.19  
# 無線機と連動できる音声chat server

# 使い方:  
1)事前にLM studio serverを起動しておく。modelは日本語学習したものを使う事。それと同じモデル名を下記ソースにも設定しておく。  
2)事前にVOICEVOX coreを起動しておく。"C:\Program Files\VOICEVOX\vv-engine\run.exe" --host 127.0.0.1  
3)COMポートのDTRで無線機のPTTコントロールをしたい場合は -c COM7 のように起動パラメーターで指定する。SignaLINKやVOXの場合は不要です。  
4)起動したらオーディオ入力デバイスID番号と、同出力デバイスIDを指定する。  
5)ctrl+cで終了する。  
 
# 動作説明：    
1)音声をgoogle recognizerに渡す。  
2)帰ってきたテキストをLM studio serverに渡す。LM studio server側は日本語モデルであること。英語モデルに渡すと英語で返答してしまう。  
3)LM studio serverの返答をVOICEVOXに渡す。  
4)VOICEVOXから返ってきた音声データーをオーディオ出力デバイスにストリーミング再生する。  
5)ストリーミング再生中、-c で指定されたCOMポートのDTRをONにする(=無線機は送信状態になる)。ストリーミング終了でDTRをOFFにする(=無線機は受信状態に戻る)。  

# 使い方のコツ：  
あんまり送信時間が長いと怪しまれるので、LM studio serverの tokens to generate n_gpu_layers の値を20～50ぐらいにしておいたほうが良い。(50トークン ≒ 50文字)  
# 
# 既知のバグ：  
バグというか・・・アルファベットを話されると、日本語モデルのくせに(笑)英語を返してくる。VOICEVOXがそれをアルファベット一文字ずつ読み始めて収拾がつかなくなる。  
そうなったらこのプログラムを強制終了して、布団かぶって寝るか再起動する。  
