# -*- coding: utf-8 -*-
"""
vintage_pomodoro MSIX 패키징 오케스트레이터
(23_app_Releaser LaunchPad의 MsixPackagingService 레시피 재현:
 manifest 생성 -> 자체서명 인증서 -> makeappx -> signtool)
"""
import os
import shutil
import subprocess
import sys
from PIL import Image

APP_NAME = "Vintage Pomodoro"
PKG_NAME = "delight0517-VintagePomodoro"
DISPLAY_NAME = "Vintage Pomodoro"
VERSION = "0.2.3.0"                      # pubspec 0.2.3+7 → 4세그먼트
CERT_SUBJECT = "CN=LaunchPadSelfSigned"   # LaunchPad와 동일 인증서 재사용
CERT_PFX = os.path.join(os.environ["LOCALAPPDATA"], "LaunchPad", "cert", "launchpad_selfsigned.pfx")
CERT_PWD = "launchpad-dev"

RELEASE_DIR = r"C:\Users\delig\Desktop\app dev\timer1\build\windows\x64\runner\Release"
STAGING = r"C:\Users\delig\vintage-pomodoro-site\msix-staging"
ICO = r"C:\Users\delig\Desktop\app dev\timer1\windows\runner\resources\app_icon.ico"
OUT_DIR = r"C:\Users\delig\vintage-pomodoro-site\msix-output"
MSIX = os.path.join(OUT_DIR, PKG_NAME + "-" + VERSION + ".msix")

SDK_BIN = r"C:\Program Files (x86)\Windows Kits\10\bin\10.0.26100.0\x64"
MAKEAPPX = os.path.join(SDK_BIN, "makeappx.exe")
SIGNTOOL = os.path.join(SDK_BIN, "signtool.exe")


def log(msg):
    print("[MSIX]", msg, flush=True)


def run(cmd, **kw):
    log("$ " + " ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True, **kw)
    if r.stdout and r.stdout.strip():
        print(r.stdout.strip()[-1200:])
    if r.returncode != 0:
        print(r.stderr.strip()[-800:], file=sys.stderr)
        raise SystemExit(f"실패(exit {r.returncode}): {cmd[0]}")
    return r


# 1) 스테이징 준비
if os.path.exists(STAGING):
    shutil.rmtree(STAGING)
shutil.copytree(RELEASE_DIR, STAGING)
log(f"스테이징 복사 완료: {STAGING}")

# 2) 아이콘 에셋 생성 (ico → 44/150/50 png)
img = Image.open(ICO).convert("RGBA")
assets = os.path.join(STAGING, "Assets")
os.makedirs(assets, exist_ok=True)
for size, name in [(44, "Square44x44Logo.png"), (150, "Square150x150Logo.png"), (50, "StoreLogo.png")]:
    img.resize((size, size), Image.LANCZOS).save(os.path.join(assets, name))
log("아이콘 에셋 생성 완료 (44/150/50)")

# 3) AppxManifest.xml
manifest = f"""<?xml version="1.0" encoding="utf-8"?>
<Package
  xmlns="http://schemas.microsoft.com/appx/manifest/foundation/windows10"
  xmlns:uap="http://schemas.microsoft.com/appx/manifest/uap/windows10"
  xmlns:rescap="http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities"
  IgnorableNamespaces="uap rescap">

  <Identity Name="{PKG_NAME}" Publisher="{CERT_SUBJECT}" Version="{VERSION}" />

  <Properties>
    <DisplayName>{DISPLAY_NAME}</DisplayName>
    <PublisherDisplayName>delight0517</PublisherDisplayName>
    <Logo>Assets\\StoreLogo.png</Logo>
  </Properties>

  <Dependencies>
    <TargetDeviceFamily Name="Windows.Desktop" MinVersion="10.0.17763.0" MaxVersionTested="10.0.22000.0" />
  </Dependencies>

  <Resources>
    <Resource Language="ko-kr" />
    <Resource Language="en-us" />
  </Resources>

  <Applications>
    <Application Id="App" Executable="vintage_pomodoro.exe" EntryPoint="Windows.FullTrustApplication">
      <uap:VisualElements
        DisplayName="{DISPLAY_NAME}"
        Description="빈티지 포모도로 타이머 - 방해 없는 25분과 강제 잠금 휴식"
        BackgroundColor="#EEEAE0"
        Square150x150Logo="Assets\\Square150x150Logo.png"
        Square44x44Logo="Assets\\Square44x44Logo.png">
      </uap:VisualElements>
    </Application>
  </Applications>

  <Capabilities>
    <rescap:Capability Name="runFullTrust" />
  </Capabilities>
</Package>
"""
with open(os.path.join(STAGING, "AppxManifest.xml"), "w", encoding="utf-8") as f:
    f.write(manifest)
log("AppxManifest.xml 생성 완료")

# 4) 자체서명 인증서 (없으면 생성 — LaunchPad와 동일 방식)
if not os.path.exists(CERT_PFX):
    log("자체서명 인증서 새로 생성...")
    ps = f'''
$cert = New-SelfSignedCertificate -Type Custom -Subject "{CERT_SUBJECT}" `
    -KeyUsage DigitalSignature -FriendlyName "LaunchPad Self-Signed" `
    -CertStoreLocation "Cert:\\CurrentUser\\My" `
    -TextExtension @("2.5.29.37={{text}}1.3.6.1.5.5.7.3.3","2.5.29.19={{text}}") `
    -KeyAlgorithm RSA -KeyLength 2048 -NotAfter (Get-Date).AddYears(3)
$pwd = ConvertTo-SecureString -String "{CERT_PWD}" -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath "{CERT_PFX}" -Password $pwd | Out-Null
'''
    tmp = os.path.join(os.environ["TEMP"], "vp_makecert.ps1")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(ps)
    run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", tmp])
else:
    log("기존 인증서 재사용: " + CERT_PFX)

# 5) makeappx 패키징
os.makedirs(OUT_DIR, exist_ok=True)
run([MAKEAPPX, "pack", "/o", "/d", STAGING, "/p", MSIX])
log("makeappx 완료: " + MSIX)

# 6) signtool 서명
run([SIGNTOOL, "sign", "/fd", "SHA256", "/a", "/f", CERT_PFX, "/p", CERT_PWD, MSIX])
log("signtool 서명 완료")

# 7) 검증 + 요약
run([SIGNTOOL, "verify", "/pa", MSIX.replace("\\", "/")] if False else [SIGNTOOL, "verify", "/pa", MSIX])
size_mb = os.path.getsize(MSIX) / 1024 / 1024
print()
print("=" * 56)
print(f"🎉 MSIX 완성: {MSIX}")
print(f"   크기: {size_mb:.1f} MB | 버전: {VERSION} | 서명: {CERT_SUBJECT}")
print("=" * 56)
