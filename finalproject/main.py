from typing import List, Optional
from fastapi import FastAPI, HTTPException, Query, Path, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, ValidationError

app = FastAPI(title="MediCare Clinic API", version="1.0", debug=True)

@app.exception_handler(ValidationError)
async def validation_exception_handler(request: Request, exc: ValidationError):
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "error": "Validation Error"}
    )

# 1. initial root
@app.get("/")
def home():
    return {"message": "Welcome to MediCare Clinic"}

# 2. doctors list
doctors = [
    {"id": 1, "name": "Dr. Asha Sharma", "specialization": "Cardiologist", "fee": 1500, "experience_years": 12, "is_available": True},
    {"id": 2, "name": "Dr. Rajiv Gupta", "specialization": "Dermatologist", "fee": 1100, "experience_years": 10, "is_available": True},
    {"id": 3, "name": "Dr. Meera Patel", "specialization": "Pediatrician", "fee": 1300, "experience_years": 8, "is_available": False},
    {"id": 4, "name": "Dr. Sunil Khanna", "specialization": "General", "fee": 900, "experience_years": 15, "is_available": True},
    {"id": 5, "name": "Dr. Anita Verma", "specialization": "Cardiologist", "fee": 1700, "experience_years": 20, "is_available": False},
    {"id": 6, "name": "Dr. Nisha Rao", "specialization": "Dermatologist", "fee": 1050, "experience_years": 6, "is_available": True},
]

# 4. appointments and counter
appointments: List[dict] = []
appt_counter = 1

# 6. AppointmentRequest model
class AppointmentRequest(BaseModel):
    patient_name: str = Field(..., min_length=2)
    doctor_id: int = Field(..., gt=0)
    date: str = Field(..., min_length=8)
    reason: str = Field(..., min_length=5)
    appointment_type: str = Field("in-person")
    senior_citizen: bool = False

    @field_validator('appointment_type')
    @classmethod
    def validate_appointment_type(cls, v):
        allowed_types = ["in-person", "video", "emergency"]
        if v not in allowed_types:
            raise ValueError(f"appointment_type must be one of: {', '.join(allowed_types)}")
        return v

# 7. helper functions

def find_doctor(doctor_id: int) -> Optional[dict]:
    return next((doc for doc in doctors if doc["id"] == doctor_id), None)


def calculate_fee(base_fee: int, appointment_type: str, senior_citizen: bool) -> dict:
    if appointment_type == "video":
        fee = int(base_fee * 0.8)
    elif appointment_type == "emergency":
        fee = int(base_fee * 1.5)
    else:
        fee = base_fee

    original_fee = fee
    if senior_citizen:
        discounted_fee = int(fee * 0.85)
    else:
        discounted_fee = fee

    return {
        "original_fee": original_fee,
        "discounted_fee": discounted_fee,
        "appointment_type": appointment_type,
        "senior_citizen": senior_citizen,
    }

# 2. GET /doctors
@app.get("/doctors")
def get_doctors():
    total = len(doctors)
    available_count = len([d for d in doctors if d["is_available"]])
    return {"doctors": doctors, "total": total, "available_count": available_count}

# 11. POST /doctors (NewDoctor)
class NewDoctor(BaseModel):
    name: str = Field(..., min_length=2)
    specialization: str = Field(..., min_length=2)
    fee: int = Field(..., gt=0)
    experience_years: int = Field(..., gt=0)
    is_available: bool = True

@app.post("/doctors", status_code=201)
def create_doctor(new_doctor: NewDoctor):
    if any(d["name"].lower() == new_doctor.name.lower() for d in doctors):
        raise HTTPException(status_code=400, detail="Doctor with this name already exists")

    new_id = max((d["id"] for d in doctors), default=0) + 1
    doctor_data = new_doctor.dict()
    doctor_data["id"] = new_id
    doctors.append(doctor_data)
    return doctor_data

# 5. GET /doctors/summary
@app.get("/doctors/summary")
def doctors_summary():
    total = len(doctors)
    available_count = len([d for d in doctors if d["is_available"]])
    most_experienced = max(doctors, key=lambda d: d["experience_years"]) if doctors else None
    cheapest_fee = min(doctors, key=lambda d: d["fee"])["fee"] if doctors else None
    per_specialization = {}
    for d in doctors:
        per_specialization[d["specialization"]] = per_specialization.get(d["specialization"], 0) + 1

    return {
        "total_doctors": total,
        "available_count": available_count,
        "most_experienced_doctor": most_experienced["name"] if most_experienced else None,
        "cheapest_fee": cheapest_fee,
        "count_per_specialization": per_specialization,
    }


# 4. GET /appointments
@app.get("/appointments")
def get_appointments():
    return {"appointments": appointments, "total": len(appointments)}

# 8. POST /appointments
@app.post("/appointments", status_code=201)
def create_appointment(appt: AppointmentRequest):
    global appt_counter

    doctor = find_doctor(appt.doctor_id)
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")
    if not doctor["is_available"]:
        raise HTTPException(status_code=400, detail="Doctor is not available")

    fee_info = calculate_fee(doctor["fee"], appt.appointment_type, appt.senior_citizen)

    appointment = {
        "appointment_id": appt_counter,
        "patient_name": appt.patient_name,
        "doctor_id": appt.doctor_id,
        "doctor_name": doctor["name"],
        "date": appt.date,
        "reason": appt.reason,
        "appointment_type": appt.appointment_type,
        "status": "scheduled",
        "original_fee": fee_info["original_fee"],
        "discounted_fee": fee_info["discounted_fee"],
        "senior_citizen": appt.senior_citizen,
    }
    appointments.append(appointment)
    appt_counter += 1
    doctor["is_available"] = False

    return appointment


# 10. filter helper and endpoint
@app.get("/doctors/filter")
def filter_doctors(
    specialization: Optional[str] = Query(None),
    max_fee: Optional[int] = Query(None, gt=0),
    min_experience: Optional[int] = Query(None, gt=0),
    is_available: Optional[bool] = Query(None),
):
    result = doctors
    if specialization is not None:
        result = [d for d in result if d["specialization"].lower() == specialization.lower()]
    if max_fee is not None:
        result = [d for d in result if d["fee"] <= max_fee]
    if min_experience is not None:
        result = [d for d in result if d["experience_years"] >= min_experience]
    if is_available is not None:
        result = [d for d in result if d["is_available"] == is_available]
    return {"results": result, "count": len(result)}

# 12. PUT /doctors/{doctor_id}
@app.put("/doctors/{doctor_id}")
def update_doctor_info(
    doctor_id: int,
    fee: Optional[int] = Query(None, gt=0),
    is_available: Optional[bool] = Query(None),
):
    doctor = find_doctor(doctor_id)
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")
    if fee is not None:
        doctor["fee"] = fee
    if is_available is not None:
        doctor["is_available"] = is_available
    return doctor

# 13. DELETE /doctors/{doctor_id}
@app.delete("/doctors/{doctor_id}")
def delete_doctor_by_id(doctor_id: int):
    doctor = find_doctor(doctor_id)
    if doctor is None:
        raise HTTPException(status_code=404, detail="Doctor not found")
    scheduled = [a for a in appointments if a["doctor_id"] == doctor_id and a["status"] == "scheduled"]
    if scheduled:
        raise HTTPException(status_code=400, detail="Doctor has scheduled appointments")
    doctors.remove(doctor)
    return {"message": "Doctor deleted"}

# 16. doctors/search
@app.get("/doctors/search")
def doctors_search(keyword: str = Query(..., min_length=1)):
    low = keyword.lower()
    result = [d for d in doctors if low in d["name"].lower() or low in d["specialization"].lower()]
    if not result:
        return {"message": f"No doctors found for keyword '{keyword}'"}
    return {"results": result, "total_found": len(result)}

# 19. appointments search/sort/page
@app.get("/appointments/search")
def appointments_search(patient_name: str = Query(..., min_length=1)):
    low = patient_name.lower()
    result = [a for a in appointments if low in a["patient_name"].lower()]
    if not result:
        return {"message": f"No appointments found for patient '{patient_name}'"}
    return {"appointments": result, "total_found": len(result)}

@app.get("/appointments/sort")
def appointments_sort(
    sort_by: str = Query("date", pattern="^(date|fee)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
):
    reverse = order == "desc"
    if sort_by == "fee":
        key = lambda a: a["discounted_fee"]
    else:
        key = lambda a: a["date"]
    result = sorted(appointments, key=key, reverse=reverse)
    return {"sorted_by": sort_by, "order": order, "appointments": result}

@app.get("/appointments/page")
def appointments_page(page: int = Query(1, ge=1), limit: int = Query(5, ge=1)):
    total = len(appointments)
    total_pages = (total + limit - 1) // limit
    start = (page - 1) * limit
    segment = appointments[start:start + limit]
    return {"page": page, "limit": limit, "total": total, "total_pages": total_pages, "appointments": segment}



# 20. doctors/browse
@app.get("/doctors/browse")
def doctors_browse(
    keyword: Optional[str] = Query(None),
    sort_by: str = Query("fee", pattern="^(fee|name|experience_years)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
    page: int = Query(1, ge=1),
    limit: int = Query(4, ge=1),
):
    result = doctors
    if keyword:
        low = keyword.lower()
        result = [d for d in result if low in d["name"].lower() or low in d["specialization"].lower()]

    reverse = order == "desc"
    result = sorted(result, key=lambda d: d[sort_by], reverse=reverse)

    total = len(result)
    total_pages = (total + limit - 1) // limit
    start = (page - 1) * limit
    segment = result[start:start + limit]
    return {
        "keyword": keyword,
        "sort_by": sort_by,
        "order": order,
        "page": page,
        "limit": limit,
        "total_found": total,
        "total_pages": total_pages,
        "doctors": segment,
    }


# 18. doctors/page
@app.get("/doctors/page")
def doctors_page(page: int = Query(1, ge=1), limit: int = Query(3, ge=1)):
    total = len(doctors)
    total_pages = (total + limit - 1) // limit
    start = (page - 1) * limit
    segment = doctors[start:start + limit]
    return {"page": page, "limit": limit, "total": total, "total_pages": total_pages, "doctors": segment}


# 3. GET /doctors/{doctor_id}
@app.get("/doctors/{doctor_id}")
def get_doctor_by_id(doctor_id: int = Path(..., gt=0)):
    doctor = find_doctor(doctor_id)
    if not doctor:
        raise HTTPException(status_code=404, detail="Doctor not found")
    return doctor

# 14. confirm/cancel appointment
@app.post("/appointments/{appointment_id}/confirm")
def confirm_appointment(appointment_id: int):
    appointment = next((a for a in appointments if a["appointment_id"] == appointment_id), None)
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    appointment["status"] = "confirmed"
    return appointment

@app.post("/appointments/{appointment_id}/cancel")
def cancel_appointment(appointment_id: int):
    appointment = next((a for a in appointments if a["appointment_id"] == appointment_id), None)
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    appointment["status"] = "cancelled"
    doctor = find_doctor(appointment["doctor_id"])
    if doctor:
        doctor["is_available"] = True
    return appointment

# 15. complete + active + by-doctor
@app.post("/appointments/{appointment_id}/complete")
def complete_appointment(appointment_id: int):
    appointment = next((a for a in appointments if a["appointment_id"] == appointment_id), None)
    if appointment is None:
        raise HTTPException(status_code=404, detail="Appointment not found")
    appointment["status"] = "completed"
    return appointment

@app.get("/appointments/active")
def active_appointments():
    result = [a for a in appointments if a["status"] in ["scheduled", "confirmed"]]
    return {"appointments": result, "total": len(result)}

@app.get("/appointments/by-doctor/{doctor_id}")
def appointments_by_doctor(doctor_id: int):
    result = [a for a in appointments if a["doctor_id"] == doctor_id]
    return {"appointments": result, "total": len(result)}


# 17. doctors/sort
@app.get("/doctors/sort")
def doctors_sort(
    sort_by: str = Query("fee", pattern="^(fee|name|experience_years)$"),
    order: str = Query("asc", pattern="^(asc|desc)$"),
):
    reverse = order == "desc"
    result = sorted(doctors, key=lambda d: d[sort_by], reverse=reverse)
    return {"sorted_by": sort_by, "order": order, "doctors": result}

