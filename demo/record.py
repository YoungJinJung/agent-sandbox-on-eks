"""Capture actual demo PTY output and presenter Enter inputs with timestamps."""
import codecs,fcntl,json,os,pty,select,signal,struct,subprocess,sys,termios,time
from pathlib import Path
if len(sys.argv) != 2: raise SystemExit('Usage: python3 demo/record.py <new-output-directory>')
out=Path(sys.argv[1]); out.mkdir(parents=True,exist_ok=False)
master,slave=pty.openpty()
fcntl.ioctl(slave,termios.TIOCSWINSZ,struct.pack('HHHH',42,132,0,0))
env=os.environ.copy(); env.update(PYTHONUNBUFFERED='1',TERM='xterm-256color',NO_COLOR='1')
start=time.monotonic(); events=[]; text=''; sent=0; schedule=[1,38,57,92]; stopping=False
timeline_started=False; preflight=''
p=subprocess.Popen(['./demo/run.sh'],stdin=slave,stdout=slave,stderr=slave,env=env,start_new_session=True)
os.close(slave); decoder=codecs.getincrementaldecoder('utf-8')('replace')
try:
 while True:
  elapsed=time.monotonic()-start
  if elapsed>240 and not stopping:
   os.killpg(p.pid,signal.SIGTERM); stopping=True
  if elapsed>420 and p.poll() is None:
   os.killpg(p.pid,signal.SIGKILL)
   raise RuntimeError('Recording timed out; inspect the cluster and run demo cleanup')
  ready,_,_=select.select([master],[],[],0.1)
  if ready:
   try: raw=os.read(master,65536)
   except OSError: break
   if not raw: break
   chunk=decoder.decode(raw); text+=chunk
   # Begin the talk clock after off-stage pool/port checks reach the first prompt.
   if not timeline_started and not stopping and '[Enter] 다음 단계' in text:
    preflight=text[:-len(chunk)]; start=time.monotonic(); elapsed=0; events=[]; timeline_started=True
   events.append([round(elapsed,3),'o',chunk])
  if not stopping and sent<4 and text.count('[Enter] 다음 단계')>sent and elapsed>=schedule[sent]:
   os.write(master,b'\n');events.append([round(elapsed,3),'i','\n']);sent+=1
  if p.poll() is not None and not ready: break
except BaseException:
 # Keep the PTY open while the stage driver's finally block cleans up AWS work.
 if p.poll() is None:
  os.killpg(p.pid,signal.SIGTERM)
  try: p.wait(timeout=180)
  except subprocess.TimeoutExpired:
   os.killpg(p.pid,signal.SIGKILL); p.wait()
 raise
finally:
 os.close(master)
 if p.poll() is None: p.wait(timeout=75)
 capture={'command':'./demo/run.sh','utc_recorded_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'preflight':preflight,'width':132,'height':42,'duration':round(time.monotonic()-start,3),'exit_code':p.returncode,'events':events}
 (out/'capture.json').write_text(json.dumps(capture,ensure_ascii=False,indent=2))
 (out/'terminal.txt').write_text(text)
 print('Recording:',out,'exit:',p.returncode,'seconds:',capture['duration'])
 if p.returncode: print(text[-4000:])
raise SystemExit(p.returncode)
