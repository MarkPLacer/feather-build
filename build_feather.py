"""Build unmodified pinned Feather sources; report the actual SDK/Xcode build.

Produces an ad-hoc signed IPA for later re-signing. No Apple account, personal
signing key, provisioning profile or GitHub write token is used by this build.
"""
from pathlib import Path
import hashlib,json,os,plistlib,shutil,subprocess,urllib.request,zipfile
ROOT=Path.cwd();OUT=ROOT/'output';OUT.mkdir(exist_ok=True)
COMMIT='7078b053c0af262809a48e4d3898d42b0d35fedf'

def run(args,**kwargs):
    return subprocess.run(list(map(str,args)),check=True,**kwargs)

def output(args,env=None):
    return subprocess.check_output(list(map(str,args)),text=True,env=env).strip()

# A default Xcode symlink can refer to an older SDK. Inspect real installations.
candidates=[];seen=set()
for app in Path('/Applications').glob('Xcode*.app'):
    app=app.resolve()
    if app in seen:continue
    seen.add(app);env={**os.environ,'DEVELOPER_DIR':str(app/'Contents/Developer')}
    try:
        version=output(['/usr/bin/xcrun','--sdk','iphoneos','--show-sdk-version'],env)
        if version!='27.2':continue
        sdk=Path(output(['/usr/bin/xcrun','--sdk','iphoneos','--show-sdk-path'],env))
        with (sdk/'SDKSettings.plist').open('rb') as f:settings=plistlib.load(f)
        info=output(['/usr/bin/xcodebuild','-version'],env)
        candidates.append((settings.get('CanonicalName',''),info,app,env,sdk))
    except (subprocess.CalledProcessError,OSError):continue
if not candidates:raise SystemExit('No iOS 27.2 SDK installed on this runner; no older SDK silently substituted.')
# Prefer the newest numbered build, including RC when the image has received it.
import re
def key(candidate):
    build=candidate[1].split('Build version ')[-1].strip()
    # Apple beta build numbers may be numerically larger than a later RC.
    final_or_rc=re.fullmatch(r'\d+[A-Z]\d+',build) is not None
    parts=tuple(int(x) if x.isdigit() else x for x in re.findall(r'\d+|[A-Za-z]+',build))
    return final_or_rc,parts
_,xcode,app,env,sdk=max(candidates,key=key)
print(xcode,flush=True);print('SDK:',sdk.name,flush=True)
SRC=ROOT/'feather';run(['git','clone','--recurse-submodules','https://github.com/claration/feather.git',SRC]);run(['git','checkout','--detach',COMMIT],cwd=SRC);run(['git','submodule','update','--init','--recursive'],cwd=SRC)
assert output(['git','-C',SRC,'rev-parse','HEAD'])==COMMIT
# Match upstream's public loopback TLS resources without printing key material.
with urllib.request.urlopen('https://backloop.dev/pack.json',timeout=60) as response:pack=json.load(response)
deps=SRC/'deps';deps.mkdir();(deps/'server.crt').write_text(pack['cert']);(deps/'server.pem').write_text(pack['key1']+'\n'+pack['key2']+'\n');(deps/'commonName.txt').write_text(pack['info']['domains']['commonName']+'\n')
# Keep a file-level record: dependency resolution metadata may legitimately refresh.
source_hashes={str(p.relative_to(SRC)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (SRC/'Feather').rglob('*') if p.is_file()}
log=OUT/'Build.log'
with log.open('wb') as f:
    result=subprocess.run(['/usr/bin/xcodebuild','-project','Feather.xcodeproj','-scheme','Feather','-configuration','Release','-jobs','3','-destination','generic/platform=iOS','-sdk',str(sdk),'-derivedDataPath',str(ROOT/'DerivedData'),'-skipPackagePluginValidation','CODE_SIGNING_ALLOWED=NO','ALWAYS_EMBED_SWIFT_STANDARD_LIBRARIES=NO','IPHONEOS_DEPLOYMENT_TARGET=16.0'],cwd=SRC,env=env,stdout=f,stderr=subprocess.STDOUT)
if result.returncode:
    print(log.read_text(errors='replace')[-20000:]);raise SystemExit(result.returncode)
apps=list((SRC/'_build/Applications').glob('*.app'));assert len(apps)==1
payload=ROOT/'Payload';payload.mkdir();bundle=payload/'Feather.app';shutil.copytree(apps[0],bundle,symlinks=True)
for q in deps.iterdir():shutil.copy2(q,bundle/q.name)
# Sign nested code first; final app seal includes the upstream TLS resources.
frameworks=bundle/'Frameworks'
if frameworks.exists():
    for q in frameworks.iterdir():
        if q.suffix in ('.framework','.dylib'):run(['/usr/bin/codesign','--force','--sign','-','--timestamp=none',q])
run(['/usr/bin/codesign','--force','--sign','-','--timestamp=none','--entitlements',SRC/'Feather/Supporting Files/Feather.entitlements',bundle]);run(['/usr/bin/codesign','--verify','--deep','--strict',bundle])
info=plistlib.loads((bundle/'Info.plist').read_bytes());assert info.get('DTSDKName','').startswith('iphoneos27.2');assert tuple(map(int,info['MinimumOSVersion'].split('.'))) <= (27,0,1)
assert output(['/usr/bin/lipo','-archs',bundle/info['CFBundleExecutable']]) == 'arm64'
assert set(info['UIDeviceFamily']) == {1,2}
assert (bundle/'Assets.car').is_file()
assert (bundle/'Feather.momd/Feather.mom').is_file()
assert (bundle/'Launch Screen.storyboardc/Info.plist').is_file()
assert (bundle/'en.lproj/Localizable.strings').is_file()
assert all(hashlib.sha256((SRC/p).read_bytes()).hexdigest()==h for p,h in source_hashes.items()), 'Application source or resources changed during build'
build_version=output(['/usr/bin/xcrun','vtool','-show-build',bundle/info['CFBundleExecutable']],env)
assert re.search(r'platform\s+IOS\b',build_version)
assert re.search(r'sdk\s+27\.2\b',build_version)
ipa=OUT/'Feather-7078b05-iOS27.2.ipa';run(['/usr/bin/ditto','-c','-k','--keepParent',payload,ipa])
with zipfile.ZipFile(ipa) as z:assert z.testzip() is None
provenance={'repository':'https://github.com/claration/feather','source_commit':COMMIT,'application_sources_and_resources_unchanged':True,'source_status':output(['git','-C',SRC,'status','--porcelain']),'submodules':output(['git','-C',SRC,'submodule','status']),'xcode':xcode,'sdk':info.get('DTSDKName'),'sdk_build':info.get('DTSDKBuild'),'platform_build':info.get('DTPlatformBuild'),'macho_build_version':build_version,'codesign_deep_strict_verified':True,'device_families':info['UIDeviceFamily'],'minimum_os':info['MinimumOSVersion'],'version':info.get('CFBundleShortVersionString'),'signing':'ad-hoc; requires re-signing for ordinary device installation','sha256':hashlib.sha256(ipa.read_bytes()).hexdigest(),'latest_official_xcode_at_preparation':'27.2 RC (27B48)','exact_latest_rc_used':'27B48' in xcode,'physical_device_tested':False}
(OUT/'Build-Info.json').write_text(json.dumps(provenance,indent=2)+'\n');(OUT/'SHA256SUMS.txt').write_text(provenance['sha256']+'  '+ipa.name+'\n');print(json.dumps(provenance,indent=2))
