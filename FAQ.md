# Frequently Asked Questions (FAQ)

## 📋 Text Injection & Applications

### Text is not appearing in Notepad (or appears twice)
This is usually a **Clipboard Timing** issue. Some applications (like Classic Notepad) are slower to register clipboard changes.
- **Fix**: Go to **Settings → Advanced** and increase the **Injection delay (ms)** to **50ms** or **100ms**. This gives the app more time to "see" the new text before the paste command is fired.

### Dictation doesn't work in my Terminal or Password Manager
Some apps block the standard "Clipboard Paste" method for security reasons.
- **Fix**: Go to **Settings → Advanced** and change the **Text injection method** to **sendinput**. This types the text character-by-character, simulating a real keyboard.

---

## 🎙️ Audio & Recording

### The app says "Listening" but no text appears
This is often caused by **Windows Privacy Settings**.
- **Fix**: Open Windows Settings → **Privacy & security** → **Microphone**. Ensure that "Microphone access" is **On** and that "Let desktop apps access your microphone" is also **On**.
- **Diagnostic**: Use the **Test Microphone** button in **Settings → Audio** to see if the app is receiving any signal (green bar).

### Recording stops too early (or too late)
This is controlled by the Voice Activity Detection (VAD).
- **Fix**: Adjust **VAD aggressiveness** in **Settings → Audio**. A higher value (3) is more sensitive to silence; a lower value (1) is more "forgiving" of pauses in your speech.

---

## ☁️ Cloud Engines (Azure & Sarvam)

### Sarvam AI: "Error 400: Audio duration exceeds limit"
Sarvam AI has a hard limit of **30 seconds** for real-time transcription.
- **Fix**: In **Settings → Audio**, ensure your **Max recording length** is set to 30 seconds or less.

### "No Azure key stored" or "Connection failed"
API keys are stored in the **Windows Credential Manager**. If you recently changed your Windows password or migrated your profile, the key might be inaccessible.
- **Fix**: Re-enter your API key in the **Azure Cloud** or **Sarvam AI** tab and click **Save**.

---

## 🧠 AI Polishing (Ollama)

### The app hangs or gets stuck on "Polishing..."
If you are using a local LLM (Ollama), the first time you run a model it might take 20-30 seconds to load into your GPU/RAM.
- **Fix**: Check your Ollama console or use `ollama list` to ensure the model (e.g., `llama3`) is fully downloaded. Ensure your local server is running at `http://localhost:11434`.

---

---

## 🏎️ GPU & CUDA (Hardware Acceleration)

### I have an NVIDIA GPU, but the app says "cublas64_12.dll not found"
The local transcription engine (`faster-whisper`) requires specific NVIDIA libraries that aren't included with standard drivers.
- **Fix**: Open your terminal and run:
  ```powershell
  .venv\Scripts\pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
  ```
- **Note**: DictateAnywhere will automatically detect these new libraries the next time it starts and add them to the Windows path.

### How do I know if my GPU is actually being used?
1.  Open **Task Manager** → **Performance** tab.
2.  Select your **GPU** (NVIDIA).
3.  Dictate a long sentence. You should see a spike in the **Compute_0** or **CUDA** graph while the app says "Transcribing...".
4.  Alternatively, check the app's log file (`dictateanywhere.log`) for the line: `Loading faster-whisper model ... (device=cuda)`.

### Does this work on AMD or Intel GPUs?
Currently, hardware acceleration for the local engine is strictly limited to **NVIDIA GPUs** via CUDA. For AMD or Intel users, the app will automatically use the CPU (OpenMP/MKL), which is still very efficient in `int8` mode.
