"""Sinh 2 sơ đồ draw.io cho báo cáo EasyRent: use-case và kiến trúc đa đám mây."""
import sys
from xml.sax.saxutils import escape

OUT = sys.argv[1]
AZ = "img/lib/azure2/"


class Diagram:
    def __init__(self, name, w, h):
        self.name, self.w, self.h = name, w, h
        self.cells, self.n = [], 1

    def _id(self):
        self.n += 1
        return f"c{self.n}"

    def v(self, label, x, y, w, h, style, parent="1"):
        i = self._id()
        self.cells.append(
            f'<mxCell id="{i}" value="{escape(label, {chr(34): "&quot;"})}" style="{style}" vertex="1" parent="{parent}">'
            f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
        return i

    def e(self, src, dst, label="", style="", points=None, lx=None):
        i = self._id()
        pts = ""
        if points:
            pts = '<Array as="points">' + "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in points) + "</Array>"
        geo = f'<mxGeometry x="{lx}" relative="1" as="geometry">' if lx is not None else '<mxGeometry relative="1" as="geometry">'
        self.cells.append(
            f'<mxCell id="{i}" value="{escape(label, {chr(34): "&quot;"})}" style="{style}" edge="1" parent="1" source="{src}" target="{dst}">'
            f'{geo}{pts}</mxGeometry></mxCell>')
        return i

    def xml(self):
        body = "".join(self.cells)
        return (f'<mxfile host="app.diagrams.net"><diagram name="{self.name}" id="{self.name}">'
                f'<mxGraphModel dx="1400" dy="900" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" '
                f'fold="1" page="1" pageScale="1" pageWidth="{self.w}" pageHeight="{self.h}" math="0" shadow="0">'
                f'<root><mxCell id="0"/><mxCell id="1" parent="0"/>{body}</root></mxGraphModel></diagram></mxfile>')


FONT = "fontFamily=Times New Roman;"

# ---------------------------------------------------------------- use-case
def usecase():
    d = Diagram("use-case", 1100, 800)
    d.v("EASYRENT", 380, 8, 240, 34, f"text;html=1;align=center;verticalAlign=middle;fontSize=24;fontStyle=1;{FONT}")
    d.v("", 150, 50, 680, 720, "rounded=0;whiteSpace=wrap;html=1;fillColor=#dae8fc;strokeColor=#6c8ebf;")
    uc = f"ellipse;whiteSpace=wrap;html=1;fontSize=16;{FONT}fillColor=#ffffff;strokeColor=#000000;"
    W, H, P = 260, 58, 68

    def col(x, labels, y0, pitch=P):
        return [d.v(t, x, y0 + k * pitch, W, H, uc) for k, t in enumerate(labels)]

    s = col(185, ["Tìm phòng trọ (lọc, khoảng cách)", "Xem phòng trên bản đồ",
                  "So sánh phòng, chi phí mỗi tháng", "Đặt lịch xem phòng", "Yêu thích, đánh giá phòng"], 70)
    login = d.v("Đăng ký, đăng nhập (mọi vai trò)", 185, 70 + 5 * P, W, H, uc)
    c = col(185, ["Quản lý nhà, phòng, ảnh; gửi duyệt", "Xác nhận, từ chối lịch xem",
                  "Quản lý khách thuê, hợp đồng", "Ghi điện nước, lập hóa đơn"], 70 + 6 * P)
    a = col(530, ["Duyệt phòng, xác minh chủ trọ", "Xử lý báo cáo vi phạm",
                  "Giám sát hệ thống, đồng bộ lại", "Sao lưu, khôi phục thử"], 70)
    y = col(530, ["Đồng bộ tin công khai lên Azure", "Nhắc lịch xem, hóa đơn, hợp đồng",
                  "Cảnh báo sự cố tới quản trị"], 430, 100)

    actor = f"shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;html=1;outlineConnect=0;fontSize=16;{FONT}"
    sv = d.v("Sinh viên", 55, 190, 40, 80, actor)
    ct = d.v("Chủ trọ", 55, 560, 40, 80, actor)
    qt = d.v("Quản trị viên", 880, 130, 40, 80, actor)
    az = d.v("Azure Cloud<br>(Functions, Monitor)", 875, 455, 50, 50,
             f"image;aspect=fixed;html=1;points=[];labelPosition=right;verticalLabelPosition=middle;align=left;verticalAlign=middle;fontSize=15;image={AZ}compute/Function_Apps.svg;{FONT}")
    tg = d.v("Telegram Bot", 860, 640, 90, 40,
             f"rounded=1;whiteSpace=wrap;html=1;fillColor=#2AABEE;fontColor=#ffffff;strokeColor=#1C8ACB;fontSize=15;fontStyle=1;{FONT}")

    line = "endArrow=none;html=1;rounded=0;strokeWidth=1.2;"
    L = line + "entryX=0;entryY=0.5;entryDx=0;entryDy=0;"
    R = line + "entryX=1;entryY=0.5;entryDx=0;entryDy=0;"
    for t in s + [login]:
        d.e(sv, t, style=L)
    for t in c + [login]:
        d.e(ct, t, style=L)
    for t in a:
        d.e(qt, t, style=R)
    for t in y:
        d.e(az, t, style=R)
    for t in y[1:]:
        d.e(tg, t, style=R)
    return d


# ---------------------------------------------------------------- kiến trúc
def architecture():
    d = Diagram("kien-truc", 1560, 960)
    icon = lambda img, pos="bottom": (
        f"image;aspect=fixed;html=1;points=[];fontSize=13;image={img};{FONT}"
        + ("verticalLabelPosition=bottom;verticalAlign=top;align=center;" if pos == "bottom" else
           "labelPosition=right;verticalLabelPosition=middle;align=left;verticalAlign=middle;spacingLeft=2;"))
    box = lambda stroke, fill="none", dash=0, bold=1, size=15: (
        f"rounded=0;whiteSpace=wrap;html=1;strokeColor={stroke};fillColor={fill};dashed={dash};"
        f"verticalAlign=top;align=left;spacingLeft=8;fontStyle={bold};fontSize={size};{FONT}")
    svc = lambda fill, stroke: (f"rounded=1;whiteSpace=wrap;html=1;fillColor={fill};strokeColor={stroke};"
                                f"fontSize=13;align=center;verticalAlign=middle;{FONT}")
    actor = (f"shape=umlActor;verticalLabelPosition=bottom;verticalAlign=top;outlineConnect=0;html=1;"
             f"fontSize=14;{FONT}")

    # Người dùng, nhóm vận hành
    users = d.v("Người dùng<br>(sinh viên, chủ trọ,<br>quản trị)", 50, 230, 40, 80, actor)
    ops = d.v("Nhóm vận hành<br>(SSH qua Tailscale)", 50, 620, 40, 80, actor)

    # ---------------- OpenStack
    d.v("OpenStack (DevStack) – Private cloud, project <i>phongtro</i> (Keystone)", 190, 60, 650, 870, box("#ED1944", "#fff5f6", 0, 1, 17))
    router = d.v("Router r-phongtro<br>+ Floating IP<br>(Neutron)", 215, 245, 54, 54,
                 icon("img/lib/clip_art/networking/Router_Icon_128x128.png"))
    d.v("Mạng riêng net-phongtro 10.20.0.0/24 (Neutron)", 310, 95, 510, 700, box("#82b366", "#f3f9ee", 1, 0, 14))
    vmapp = d.v("vm-app (Nova, Ubuntu 24.04 từ Glance, 2 vCPU, 3 GB)<br><span style=\"font-weight:normal;font-size:12px\">"
                "sg-app: mở 80/443; SSH 22 từ Tailscale</span>", 330, 130, 470, 295, box("#666666", "#ffffff", 0, 1, 13))
    d.v("", 742, 138, 44, 32, icon("img/lib/mscae/Docker.svg"))
    web = d.v("<b>web</b><br>nginx + React", 350, 195, 125, 66, svc("#dae8fc", "#6c8ebf"))
    api = d.v("<b>api</b><br>FastAPI :8000", 350, 320, 125, 66, svc("#dae8fc", "#6c8ebf"))
    worker = d.v("<b>worker</b><br>outbox, hàng đợi, Telegram,<br>backup.sh, restore-test.sh", 610, 240, 170, 90, svc("#dae8fc", "#6c8ebf"))

    d.v("vm-data (Nova, 2 vCPU, 3 GB)<br><span style=\"font-weight:normal;font-size:12px\">"
        "sg-data: 5432, 9000 chỉ nhận từ sg-app</span>", 330, 465, 470, 300, box("#666666", "#ffffff", 0, 1, 13))
    d.v("", 742, 473, 44, 32, icon("img/lib/mscae/Docker.svg"))
    pg = d.v("<b>PostgreSQL 16</b><br>dữ liệu cá nhân", 360, 522, 110, 72,
             f"shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;size=10;fillColor=#336791;"
             f"strokeColor=#1F4E79;fontColor=#ffffff;fontSize=13;{FONT}")
    minio = d.v("<b>MinIO</b><br>ảnh phòng, hợp đồng", 530, 620, 130, 60, svc("#fff2cc", "#d6b656"))
    cron = d.v("<b>cron 02:00</b><br>backup.sh", 660, 690, 120, 56, svc("#e1d5e7", "#9673a6"))
    vol = d.v("Cinder volume vol-data 20 GB (/srv/data, có snapshot)", 330, 830, 330, 50,
              f"shape=cylinder3;whiteSpace=wrap;html=1;boundedLbl=1;size=8;fillColor=#f5f5f5;"
              f"strokeColor=#666666;fontSize=13;{FONT}")

    # ---------------- Azure
    d.v("Microsoft Azure – Public cloud (rg-phongtro, East Asia)", 960, 60, 570, 870,
        box("#0078D4", "#f2f8fd", 0, 1, 17))
    ingest = d.v("Function <i>ingest-room</i><br>(HTTP, khóa hàm)", 1010, 115, 56, 56,
                 icon(AZ + "compute/Function_Apps.svg"))
    search = d.v("AI Search<br><i>rooms-public</i>", 1230, 115, 56, 56, icon(AZ + "app_services/Search_Services.svg"))
    maps = d.v("Azure Maps<br><i>(vùng global)</i>", 1440, 115, 56, 56, icon(AZ + "iot/Azure_Maps_Accounts.svg"))

    d.v("Storage account stphongtro", 985, 290, 395, 170, box("#0078D4", "#ffffff", 1, 0, 13))
    blob_pub = d.v("Blob<br><i>public-images</i><br>(đọc công khai)", 1000, 330, 50, 50, icon(AZ + "general/Blob_Block.svg"))
    blob_bak = d.v("Blob <i>backups</i><br>(bản mã hóa)", 1150, 330, 50, 50, icon(AZ + "general/Storage_Container.svg"))
    queue = d.v("Queue<br><i>ops-ticks</i>", 1290, 330, 50, 50, icon(AZ + "general/Storage_Queue.svg"))
    timer = d.v("<i>daily-ticks-*</i> (Timer)<br>08:00, 02:00<br>+ <i>tick-now</i> (HTTP)", 1430, 330, 50, 50,
                icon(AZ + "compute/Function_Apps.svg"))

    appi = d.v("Application Insights<br><i>appi-phongtro</i>", 1010, 560, 50, 50,
               icon(AZ + "devops/Application_Insights.svg"))
    mon = d.v("Azure Monitor<br><i>4 quy tắc cảnh báo</i>", 1190, 560, 50, 50,
              icon(AZ + "management_governance/Monitor.svg"))
    logic = d.v("Action Group<br>→ Logic App", 1370, 560, 50, 50, icon(AZ + "integration/Logic_Apps.svg"))
    d.v("Cost Management<br><i>Budget US$30</i><br>(báo 50/80/100%)", 1000, 735, 50, 50,
        icon(AZ + "management_governance/Cost_Management_and_Billing.svg"))
    d.v("Key Vault<br><i>khóa, mật khẩu sao lưu</i><br>Function đọc qua<br>managed identity", 1170, 735, 50, 50, icon(AZ + "security/Key_Vaults.svg"))

    d.v("<b>Chú thích</b><br><font color=\"#000000\">━ truy cập, nội bộ OpenStack</font><br><font color=\"#2D7600\">━ đồng bộ tin công khai</font><br><font color=\"#C25E00\">━ hẹn giờ, hàng đợi, Telegram</font><br><font color=\"#7B3FA0\">━ sao lưu, khôi phục thử</font><br><font color=\"#C0392B\">━ giám sát, cảnh báo</font><br><font color=\"#0063B1\">━ tìm kiếm, bản đồ</font><br>┅ nét đứt: đọc dữ liệu, truy cập quản trị<br><i>Mọi kết nối OpenStack → Azure là chiều ra, HTTPS 443</i>", 1290, 690, 200, 165,
        f"rounded=0;whiteSpace=wrap;html=1;align=left;verticalAlign=top;spacingLeft=6;spacingTop=2;"
        f"fillColor=#ffffff;strokeColor=#999999;fontSize=11;{FONT}")
    tg = d.v("Telegram Bot API<br><span style=\"font-weight:normal;font-size:12px\">(tới người dùng, nhóm quản trị)</span>", 1080, 866, 210, 48,
             f"rounded=1;whiteSpace=wrap;html=1;fillColor=#2AABEE;fontColor=#ffffff;strokeColor=#1C8ACB;"
             f"fontSize=14;fontStyle=1;{FONT}")

    # ---------------- Cạnh
    def S(color, dash=0, w=1.5, ortho=True, ex=None, ey=None, nx=None, ny=None):
        s = (f"endArrow=block;endFill=1;html=1;rounded=0;strokeColor={color};dashed={dash};strokeWidth={w};"
             f"fontSize=12;fontColor={color};{FONT}labelBackgroundColor=#ffffff;")
        if ortho:
            s += "edgeStyle=orthogonalEdgeStyle;"
        if ex is not None:
            s += f"exitX={ex};exitY={ey};exitDx=0;exitDy=0;"
        if nx is not None:
            s += f"entryX={nx};entryY={ny};entryDx=0;entryDy=0;"
        return s

    BLACK, GREEN, ORANGE, PURPLE, RED, BLUE, GREY = ("#000000", "#2D7600", "#C25E00", "#7B3FA0",
                                                     "#C0392B", "#0063B1", "#555555")
    # Người dùng và nội bộ OpenStack
    d.e(users, router, "HTTP 80 / 443<br>(qua Tailscale)", S(BLACK, 0, 2, False), lx=-0.1)
    d.e(router, web, "", S(BLACK, nx=0, ny=0.5), points=[(300, 272), (300, 228)])
    d.e(web, api, "/api/*", S(BLACK, ex=0.5, ey=1, nx=0.5, ny=0))
    d.e(api, pg, "5432", S(BLACK, ex=0, ey=0.75, nx=0.5, ny=0), points=[(320, 370), (320, 508), (415, 508)], lx=0.55)
    d.e(api, minio, "9000", S(BLACK, ex=1, ey=0.5, nx=0.5, ny=0), points=[(595, 353)])
    d.e(worker, pg, "", S(BLACK, 1, ex=0.3, ey=1, nx=1, ny=0.5), points=[(668, 558)])
    d.e(worker, minio, "đọc ảnh public-src", S(BLACK, 1, ex=0.55, ey=1, nx=1, ny=0.5), points=[(708, 650)], lx=0.55)
    d.e(pg, vol, "", "endArrow=none;html=1;dashed=1;strokeColor=#666666;edgeStyle=orthogonalEdgeStyle;"
        "exitX=0;exitY=0.5;exitDx=0;exitDy=0;entryX=0.06;entryY=0;entryDx=0;entryDy=0;", points=[(350, 558)])
    d.e(ops, vmapp, "SSH 22", S(GREY, 1, ex=1, ey=0.5, nx=0, ny=0.9), points=[(290, 660), (290, 395)], lx=-0.3)

    # OpenStack → Azure: chỉ kết nối RA (HTTPS 443)
    d.e(worker, ingest, "tin công khai<br>(khóa hàm)", S(GREEN, ex=1, ey=0.2, nx=0, ny=0.5),
        points=[(880, 258), (880, 143)], lx=0.1)
    d.e(ingest, search, "ghi chỉ mục", S(GREEN, ortho=False, ex=1, ey=0.5, nx=0, ny=0.5))
    d.e(worker, blob_pub, "ảnh công khai<br>(SAS cwdl)", S(GREEN, ex=1, ey=0.45, nx=0, ny=0.5),
        points=[(900, 280), (900, 355)], lx=0.3)
    d.e(worker, queue, "kéo tin 30 giây/lần (SAS p)", S(ORANGE, ex=1, ey=0.7, nx=0.5, ny=0),
        points=[(920, 303), (920, 268), (1315, 268)], lx=0.2)
    d.e(timer, queue, "đưa tin", S(ORANGE, ortho=False, ex=0, ey=0.5, nx=1, ny=0.5))
    d.e(cron, blob_bak, "", S(PURPLE, ex=1, ey=0.5, nx=0, ny=0.5),
        points=[(940, 718), (940, 485), (1115, 485), (1115, 355)])
    d.e(worker, blob_bak, "sao lưu mã hóa (SAS cw)<br>khôi phục thử (SAS rl)",
        S(PURPLE, ex=1, ey=0.95, nx=0, ny=0.5) + "startArrow=block;startFill=1;",
        points=[(950, 325), (950, 485), (1115, 485), (1115, 355)], lx=0.5)
    d.e(vmapp, appi, "số đo, nhật ký<br>(api, worker)", S(RED, 1, ex=1, ey=0.93, nx=0, ny=0.5),
        points=[(880, 404), (880, 585)], lx=-0.1)
    d.e(appi, mon, "", S(RED, ortho=False))
    d.e(mon, logic, "cảnh báo", S(RED, ortho=False))
    d.e(logic, tg, "", S(RED, ex=1, ey=0.5, nx=1, ny=0.5), points=[(1505, 585), (1505, 890)])
    d.e(worker, tg, "nhắc lịch, hóa đơn;<br>liên kết tài khoản (getUpdates)",
        S(ORANGE, ex=0.8, ey=1, nx=0, ny=0.5) + "startArrow=block;startFill=1;",
        points=[(748, 445), (850, 445), (850, 890)], lx=0.75)
    d.e(api, search, "tìm kiếm (khóa chỉ đọc)", S(BLUE, 1, ex=1, ey=0.25, nx=0.5, ny=0),
        points=[(600, 336), (600, 40), (1258, 40)], lx=0.35)
    d.e(users, maps, "trình duyệt tải bản đồ (Maps Web SDK)",
        S(BLUE, 1, ex=0.5, ey=0, nx=0.5, ny=0), points=[(70, 18), (1468, 18)], lx=-0.35)
    return d


for d, fname in ((usecase(), "use-case-easyrent.drawio"), (architecture(), "kien-truc-da-dam-may.drawio")):
    with open(f"{OUT}/{fname}", "w", encoding="utf-8") as f:
        f.write(d.xml())
    with open(f"{OUT}/{fname}.preview.html", "w", encoding="utf-8") as f:
        import json, html
        cfg = json.dumps({"xml": d.xml(), "highlight": "none", "nav": False, "resize": False, "toolbar": "",
                          "lightbox": False, "border": 10})
        f.write('<!doctype html><html><head><meta charset="utf-8"><base href="https://app.diagrams.net/">'
                '<style>body{margin:0;background:#fff}</style></head><body>'
                f'<div class="mxgraph" data-mxgraph="{html.escape(cfg)}"></div>'
                '<script src="https://viewer.diagrams.net/js/viewer-static.min.js"></script></body></html>')
print("ok")
