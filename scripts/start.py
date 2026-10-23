"""One local supervisor; API and native worker remain separate processes."""
import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import webbrowser

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--port',type=int,default=8000)
    parser.add_argument('--open',action='store_true')
    args=parser.parse_args()
    os.chdir(ROOT)
    from backend.config import DATA
    if not (ROOT/'dist/index.html').exists():
        raise SystemExit('Frontend build is missing. Run npm ci, then npm run build.')
    temp=DATA/'tmp';temp.mkdir(parents=True,exist_ok=True)
    os.environ['TMP']=os.environ['TEMP']=str(temp)
    from backend.engine import executable
    if not executable():print('KiCad is unavailable. Upload validation remains available; checks will fail explicitly. See README.',flush=True)
    processes=[]
    def stop(*_):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,stop)
    try:
        processes.append(subprocess.Popen([sys.executable,'-m','backend.worker'],cwd=ROOT))
        processes.append(subprocess.Popen([sys.executable,'-m','uvicorn','backend.main:app','--host','127.0.0.1','--port',str(args.port)],cwd=ROOT))
        url=f'http://127.0.0.1:{args.port}'
        print(f'CircuitCheck: {url}\nPress Ctrl+C to stop the API and worker.',flush=True)
        if args.open:
            import urllib.request
            for _ in range(30):
                try:
                    urllib.request.urlopen(url+'/api/health',timeout=1)
                    webbrowser.open(url);break
                except OSError:time.sleep(.5)
        while all(p.poll() is None for p in processes):time.sleep(.5)
        if any(p.returncode for p in processes):raise SystemExit('A service exited. Review the logs above.')
    except KeyboardInterrupt:pass
    finally:
        for p in processes:
            if p.poll() is None:p.terminate()
        for p in processes:
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:p.kill();p.wait()

if __name__=='__main__':main()
