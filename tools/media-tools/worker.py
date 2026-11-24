#!/usr/bin/env python3
"""Media worker: upscale (Real-ESRGAN), video (ffmpeg) and image (Pillow) jobs.

Usage: worker.py JOBDIR
JOBDIR/job.json holds {"kind", "params", "input", "output"}; progress is written
back to JOBDIR/job.json as {"state", "progress", "message", ...}.
"""
import json, os, subprocess, sys, time, traceback, urllib.request, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
MODELS = os.environ.get("MEDIA_MODELS_DIR") or os.path.join(os.path.expanduser("~/.local/share/odysseus-kit/media-tools"), "models")
FFMPEG = "/usr/bin/ffmpeg"
FFPROBE = "/usr/bin/ffprobe"
MAX_UPSCALE_SIDE = 3000  # px; larger inputs take too long on a CPU-only server

UPSCALE_MODELS = {
    # photos: most detail, needs care with the strength slider
    "photo": {"file": "RealESRGAN_x4plus.pth",
              "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth",
              "arch": "rrdb"},
    # fast, lighter; softer and less plastic on faces/skin
    "fast": {"file": "realesr-general-x4v3.pth",
             "url": "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesr-general-x4v3.pth",
             "arch": "general"},
}

# Quality presets: value = CRF (or quality for WebP/JPEG)
VIDEO_CRF = {"h264": {"alta": 18, "equilibrada": 21, "pequena": 24},
             "hevc": {"alta": 20, "equilibrada": 23, "pequena": 26},
             "av1": {"alta": 26, "equilibrada": 30, "pequena": 35}}
IMAGE_Q = {"webp": {"alta": 92, "equilibrada": 84, "pequena": 74},
           "jpg": {"alta": 94, "equilibrada": 88, "pequena": 80}}
TARGET_H = {"original": 0, "2160": 2160, "1440": 1440, "1080": 1080, "720": 720, "480": 480}


# ---------------------------------------------------------------- Real-ESRGAN networks
# Same architectures as xinntao/Real-ESRGAN (BSD-3). Vendored here because
# basicsr (its dependency) does not build on this Python 3.14 environment.
def _build_nets():
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    class ResidualDenseBlock(nn.Module):
        def __init__(self, num_feat=64, num_grow_ch=32):
            super().__init__()
            self.conv1 = nn.Conv2d(num_feat, num_grow_ch, 3, 1, 1)
            self.conv2 = nn.Conv2d(num_feat + num_grow_ch, num_grow_ch, 3, 1, 1)
            self.conv3 = nn.Conv2d(num_feat + 2 * num_grow_ch, num_grow_ch, 3, 1, 1)
            self.conv4 = nn.Conv2d(num_feat + 3 * num_grow_ch, num_grow_ch, 3, 1, 1)
            self.conv5 = nn.Conv2d(num_feat + 4 * num_grow_ch, num_feat, 3, 1, 1)
            self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

        def forward(self, x):
            x1 = self.lrelu(self.conv1(x))
            x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
            x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
            x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
            x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
            return x5 * 0.2 + x

    class RRDB(nn.Module):
        def __init__(self, num_feat, num_grow_ch=32):
            super().__init__()
            self.rdb1 = ResidualDenseBlock(num_feat, num_grow_ch)
            self.rdb2 = ResidualDenseBlock(num_feat, num_grow_ch)
            self.rdb3 = ResidualDenseBlock(num_feat, num_grow_ch)

        def forward(self, x):
            out = self.rdb3(self.rdb2(self.rdb1(x)))
            return out * 0.2 + x

    class RRDBNet(nn.Module):
        def __init__(self, num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4):
            super().__init__()
            self.scale = scale
            self.conv_first = nn.Conv2d(num_in_ch, num_feat, 3, 1, 1)
            self.body = nn.Sequential(*[RRDB(num_feat, num_grow_ch) for _ in range(num_block)])
            self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_up1 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_up2 = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_last = nn.Conv2d(num_feat, num_out_ch, 3, 1, 1)
            self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

        def forward(self, x):
            feat = self.conv_first(x)
            feat = feat + self.conv_body(self.body(feat))
            feat = self.lrelu(self.conv_up1(F.interpolate(feat, scale_factor=2, mode="nearest")))
            feat = self.lrelu(self.conv_up2(F.interpolate(feat, scale_factor=2, mode="nearest")))
            return self.conv_last(self.lrelu(self.conv_hr(feat)))

    class SRVGGNetCompact(nn.Module):
        def __init__(self, num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4):
            super().__init__()
            self.upscale = upscale
            body = [nn.Conv2d(num_in_ch, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)]
            for _ in range(num_conv):
                body += [nn.Conv2d(num_feat, num_feat, 3, 1, 1), nn.PReLU(num_parameters=num_feat)]
            body += [nn.Conv2d(num_feat, num_out_ch * upscale * upscale, 3, 1, 1), nn.PixelShuffle(upscale)]
            self.body = nn.Sequential(*body)

        def forward(self, x):
            out = self.body(x)
            return out + F.interpolate(x, scale_factor=self.upscale, mode="nearest")

    return RRDBNet, SRVGGNetCompact


def load_net(key, path):
    import torch
    RRDBNet, SRVGGNetCompact = _build_nets()
    if UPSCALE_MODELS[key]["arch"] == "rrdb":
        net = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    else:
        net = SRVGGNetCompact(num_in_ch=3, num_out_ch=3, num_feat=64, num_conv=32, upscale=4)
    sd = torch.load(path, map_location="cpu", weights_only=True)
    for k in ("params_ema", "params"):
        if k in sd:
            sd = sd[k]
            break
    net.load_state_dict(sd, strict=True)
    return net.eval()


def enhance_tiled(net, rgb_uint8, tile=256, pad=10, scale=4, progress=None):
    """Run the network on overlapping tiles (keeps RAM low on the CPU server)."""
    import numpy as np
    import torch
    h, w, _ = rgb_uint8.shape
    x = torch.from_numpy(rgb_uint8.transpose(2, 0, 1).copy()).float().unsqueeze(0) / 255.0
    out = torch.zeros((1, 3, h * scale, w * scale), dtype=torch.float32)
    ny, nx = -(-h // tile), -(-w // tile)
    total = ny * nx
    done = 0
    with torch.inference_mode():
        for ty in range(ny):
            for tx in range(nx):
                y0, x0 = ty * tile, tx * tile
                y1, x1 = min(y0 + tile, h), min(x0 + tile, w)
                py0, px0 = max(y0 - pad, 0), max(x0 - pad, 0)
                py1, px1 = min(y1 + pad, h), min(x1 + pad, w)
                res = net(x[:, :, py0:py1, px0:px1])
                cy0, cx0 = (y0 - py0) * scale, (x0 - px0) * scale
                ch, cw = (y1 - y0) * scale, (x1 - x0) * scale
                out[:, :, y0 * scale:y1 * scale, x0 * scale:x1 * scale] = res[:, :, cy0:cy0 + ch, cx0:cx0 + cw]
                done += 1
                if progress:
                    progress(done / total)
    arr = (out.clamp(0, 1)[0].permute(1, 2, 0).numpy() * 255.0).round().astype(np.uint8)
    return arr


def _fix_torchvision():
    pass  # kept for compatibility; no longer importing realesrgan


def write_status(jobdir, **kw):
    path = os.path.join(jobdir, "job.json")
    with open(path) as f:
        job = json.load(f)
    job.update(kw)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(job, f, ensure_ascii=False)
    os.replace(tmp, path)


def ensure_model(key):
    m = UPSCALE_MODELS[key]
    os.makedirs(MODELS, exist_ok=True)
    dst = os.path.join(MODELS, m["file"])
    if not os.path.exists(dst) or os.path.getsize(dst) < 1_000_000:
        tmp = dst + ".part"
        urllib.request.urlretrieve(m["url"], tmp)
        os.replace(tmp, dst)
    return dst


def probe(path):
    out = subprocess.run([FFPROBE, "-v", "error", "-print_format", "json", "-show_format", "-show_streams", path],
                         capture_output=True, text=True, check=True).stdout
    return json.loads(out)


# ---------------------------------------------------------------- upscale
def run_upscale(jobdir, job):
    import numpy as np
    from PIL import Image
    import torch
    torch.set_num_threads(max(1, os.cpu_count() or 2))

    p = job["params"]
    model_key = p.get("model", "photo")
    scale = 4 if int(p.get("scale", 2)) == 4 else 2
    strength = min(1.0, max(0.0, float(p.get("strength", 75)) / 100.0))  # share of AI result kept
    grain = min(6.0, max(0.0, float(p.get("grain", 1.0))))              # % film grain
    face = False  # GFPGAN deliberately off: face "restoration" is the main AI look

    src = Image.open(job["input"])
    src = src.convert("RGB")
    w, h = src.size
    if max(w, h) > MAX_UPSCALE_SIDE:
        raise RuntimeError(f"Imagem demasiado grande ({w}x{h}). Máximo {MAX_UPSCALE_SIDE} px no lado maior; reduz primeiro no Otimizador de imagens.")

    write_status(jobdir, progress=3, message="A carregar modelo")
    wpath = ensure_model(model_key)
    net = load_net(model_key, wpath)

    write_status(jobdir, progress=8, message="A ampliar (IA)")
    last = [8]

    def _prog(f):
        pct = 8 + int(f * 80)
        if pct != last[0]:
            last[0] = pct
            write_status(jobdir, progress=pct, message="A ampliar (IA)")

    ai = Image.fromarray(enhance_tiled(net, np.asarray(src), tile=256, pad=10, scale=4, progress=_prog))
    tw, th = w * scale, h * scale
    ai = ai.resize((tw, th), Image.LANCZOS)  # 4x -> 2x when needed
    write_status(jobdir, progress=90, message="A misturar com a versão natural")

    # Blend with a plain Lanczos enlargement: keeps the photo's own texture and
    # avoids the waxy, over-sharpened look of pure GAN output.
    natural = src.resize((tw, th), Image.LANCZOS)
    if strength < 1.0:
        ai = Image.blend(natural, ai, strength)
    if grain > 0:
        rng = np.random.default_rng(7)
        arr = np.asarray(ai).astype(np.float32)
        noise = rng.normal(0, grain * 2.55, (th, tw, 1)).astype(np.float32)
        arr = np.clip(arr + noise, 0, 255).astype(np.uint8)
        ai = Image.fromarray(arr)

    out = job["output"]
    fmt = "PNG" if out.lower().endswith(".png") else "JPEG"
    if fmt == "JPEG":
        ai.save(out, "JPEG", quality=95, subsampling=0, optimize=True, progressive=True,
                icc_profile=src.info.get("icc_profile"))
    else:
        ai.save(out, "PNG", optimize=True, icc_profile=src.info.get("icc_profile"))
    write_status(jobdir, progress=100, state="done", message="Pronto",
                 result={"width": tw, "height": th})


# ---------------------------------------------------------------- video
def run_video(jobdir, job):
    p = job["params"]
    info = probe(job["input"])
    vs = next((s for s in info["streams"] if s.get("codec_type") == "video"), None)
    au = next((s for s in info["streams"] if s.get("codec_type") == "audio"), None)
    if not vs:
        raise RuntimeError("O ficheiro não tem vídeo.")
    sw, sh = int(vs["width"]), int(vs["height"])
    dur = float(info["format"].get("duration") or 0)

    codec = p.get("codec", "h264")
    quality = p.get("quality", "equilibrada")
    target = str(p.get("height", "original"))
    th = TARGET_H.get(target, 0)
    if th and th >= sh:       # never upscale a video
        th = 0
    vf = []
    if th:
        tw = int(round(sw * th / sh / 2)) * 2
        vf.append(f"scale={tw}:{th}:flags=lanczos")
        ow, oh = tw, th
    else:
        ow, oh = sw, sh
    vf.append("format=yuv420p")
    crf = VIDEO_CRF[codec][quality]
    args = [FFMPEG, "-hide_banner", "-nostdin", "-y", "-i", job["input"], "-map", "0:v:0", "-map", "0:a?",
            "-map_metadata", "0", "-vf", ",".join(vf)]
    if codec == "h264":
        args += ["-c:v", "libx264", "-preset", "slow", "-crf", str(crf), "-profile:v", "high", "-tune", "film"]
    elif codec == "hevc":
        args += ["-c:v", "libx265", "-preset", "medium", "-crf", str(crf), "-tag:v", "hvc1"]
    else:
        args += ["-c:v", "libsvtav1", "-preset", "6", "-crf", str(crf)]
    if au and au.get("codec_name") in ("aac", "mp3") and p.get("audio", "copy") == "copy":
        args += ["-c:a", "copy"]
    else:
        args += ["-c:a", "aac", "-b:a", "192k"]
    args += ["-movflags", "+faststart", "-progress", "pipe:1", "-nostats", job["output"]]

    write_status(jobdir, progress=1, message="A codificar")
    errfile = tempfile.TemporaryFile(mode="w+t")
    proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=errfile, text=True)
    last = 0
    for line in proc.stdout:
        if line.startswith("out_time_us=") and dur > 0:
            try:
                t = int(line.split("=", 1)[1]) / 1e6
            except ValueError:
                continue
            pct = min(99, int(t / dur * 100))
            if pct != last:
                last = pct
                write_status(jobdir, progress=pct, message="A codificar")
    code = proc.wait()
    errfile.seek(0)
    err = errfile.read()
    errfile.close()
    if code != 0:
        raise RuntimeError("ffmpeg falhou: " + err[-400:])
    write_status(jobdir, progress=100, state="done", message="Pronto",
                 result={"width": ow, "height": oh, "codec": codec, "crf": crf, "duration": dur,
                         "source": f"{sw}x{sh}"})


# ---------------------------------------------------------------- image
def run_image(jobdir, job):
    from PIL import Image, ImageOps
    p = job["params"]
    fmt = p.get("format", "webp")
    quality = p.get("quality", "equilibrada")
    max_side = int(p.get("max_side", 0) or 0)
    keep_meta = p.get("keep_meta", "0") == "1"

    im = Image.open(job["input"])
    im = ImageOps.exif_transpose(im)
    sw, sh = im.size
    icc = im.info.get("icc_profile")
    exif = im.info.get("exif") if keep_meta else None
    if max_side and max(sw, sh) > max_side:
        im.thumbnail((max_side, max_side), Image.LANCZOS)
    write_status(jobdir, progress=40, message="A comprimir")
    out = job["output"]
    if fmt == "jpg":
        if im.mode not in ("RGB", "L"):
            im = im.convert("RGB")
        q = IMAGE_Q["jpg"][quality]
        kw = dict(quality=q, optimize=True, progressive=True, subsampling=0 if q >= 90 else 2)
        if icc: kw["icc_profile"] = icc
        if exif: kw["exif"] = exif
        im.save(out, "JPEG", **kw)
    elif fmt == "webp":
        q = IMAGE_Q["webp"][quality]
        kw = dict(quality=q, method=6)
        if im.mode not in ("RGB", "RGBA"):
            im = im.convert("RGBA" if "A" in im.getbands() else "RGB")
        if icc: kw["icc_profile"] = icc
        if exif: kw["exif"] = exif
        im.save(out, "WEBP", **kw)
    else:  # png, lossless
        kw = dict(optimize=True, compress_level=9)
        if icc: kw["icc_profile"] = icc
        if exif: kw["exif"] = exif
        im.save(out, "PNG", **kw)
    ow, oh = im.size
    write_status(jobdir, progress=100, state="done", message="Pronto",
                 result={"width": ow, "height": oh, "source": f"{sw}x{sh}"})


def main():
    jobdir = sys.argv[1]
    with open(os.path.join(jobdir, "job.json")) as f:
        job = json.load(f)
    try:
        write_status(jobdir, state="running", progress=0, message="A iniciar", started=time.time())
        kind = job["kind"]
        if kind == "upscale":
            run_upscale(jobdir, job)
        elif kind == "video":
            run_video(jobdir, job)
        elif kind == "image":
            run_image(jobdir, job)
        else:
            raise RuntimeError("tipo desconhecido: " + kind)
        out = job["output"]
        write_status(jobdir, output_size=os.path.getsize(out))
    except Exception as e:
        traceback.print_exc()
        write_status(jobdir, state="error", message=str(e)[:500])
        sys.exit(1)


if __name__ == "__main__":
    main()
