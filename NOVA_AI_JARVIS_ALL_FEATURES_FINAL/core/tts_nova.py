from __future__ import annotations
import re, threading, subprocess, sys
from .config import TTS_VOICE, TTS_RATE

class NovaTTS:
    def __init__(self, on_state=None):
        self.on_state=on_state
        self._lock=threading.Lock()
        self._proc=None
    def stop(self):
        with self._lock:
            if self._proc and self._proc.poll() is None:
                try: self._proc.terminate()
                except Exception: pass
            self._proc=None
        if self.on_state: self.on_state(False)
    def speak(self,text:str):
        clean=re.sub(r'[`*_#>•]+',' ',text or '')
        clean=re.sub(r'\s+',' ',clean).strip()
        if not clean: return
        self.stop()
        sentences=re.split(r'(?<=[.!?])\s+',clean)
        for sentence in sentences:
            if not sentence.strip(): continue
            if self.on_state: self.on_state(True)
            try:
                if sys.platform=='win32':
                    ps=("Add-Type -AssemblyName System.Speech; "
                        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                        f"$s.Rate={max(-10,min(10,int((TTS_RATE-150)/10)))}; "
                        f"$s.SelectVoiceByHints([System.Speech.Synthesis.VoiceGender]::Male,[System.Speech.Synthesis.VoiceAge]::Adult,0,'en-GB'); "
                        "$s.Speak([Console]::In.ReadToEnd())")
                    self._proc=subprocess.Popen(['powershell','-NoProfile','-NonInteractive','-Command',ps],stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    self._proc.communicate(sentence.encode('utf-8'),timeout=max(8,len(sentence)/8+4))
                else:
                    self._proc=subprocess.Popen(['say',sentence],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                    self._proc.wait(timeout=max(8,len(sentence)/8+4))
            except Exception:
                pass
            finally:
                if self.on_state: self.on_state(False)
