"""Chi phí thực tế mỗi tháng (F07, SPEC 9.5). Tính bằng hàm `room_monthly_cost` trong CSDL."""
import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import CostRate

settings = get_settings()


@dataclass
class CostInputs:
    kwh: float
    m3: float
    people: int
    vehicles: int

    @classmethod
    def defaults(cls) -> "CostInputs":
        return cls(settings.est_kwh_per_month, settings.est_water_m3_per_month, settings.est_people, settings.est_vehicles)

    def as_params(self) -> dict:
        return {"kwh": self.kwh, "m3": self.m3, "people": self.people, "vehicles": self.vehicles}


def vnd(amount: int | float) -> str:
    """3200000 -> '3.200.000đ' (SPEC 20)."""
    return f"{int(round(amount)):,}".replace(",", ".") + "đ"


def _num(x: float) -> str:
    return str(int(x)) if float(x).is_integer() else str(x).replace(".", ",")


def cost_breakdown(db: Session, room_id: uuid.UUID, inputs: CostInputs) -> dict | None:
    row = db.execute(
        text(
            "SELECT * FROM room_monthly_cost(:id, CAST(:kwh AS numeric), CAST(:m3 AS numeric), "
            "CAST(:people AS integer), CAST(:vehicles AS integer))"
        ),
        {"id": room_id, **inputs.as_params()},
    ).mappings().first()
    if row is None or row["rent"] is None:
        return None
    rates = db.get(CostRate, room_id)
    e_rate = rates.electricity_per_kwh if rates else 0
    w_mode = rates.water_mode if rates else "per_m3"
    if w_mode == "per_person":
        water_label = f"Nước ({inputs.people} người × {vnd(rates.water_per_person if rates else 0)})"
    else:
        water_label = f"Nước ({_num(inputs.m3)} m³ × {vnd(rates.water_per_m3 if rates else 0)})"
    lines = [
        {"code": "rent", "label": "Tiền phòng", "amount": row["rent"]},
        {"code": "electricity", "label": f"Điện ({_num(inputs.kwh)} kWh × {vnd(e_rate)})", "amount": row["electricity"]},
        {"code": "water", "label": water_label, "amount": row["water"]},
        {"code": "internet", "label": "Internet", "amount": row["internet"]},
        {"code": "parking", "label": f"Gửi xe ({inputs.vehicles} xe)", "amount": row["parking"]},
        {"code": "service", "label": "Dịch vụ", "amount": row["service"]},
    ]
    return {"inputs": inputs.as_params(), "lines": lines, "total": row["total"]}
