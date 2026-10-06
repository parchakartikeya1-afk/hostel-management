from flask import Flask, render_template, request, redirect, url_for, flash
from database import get_db

app = Flask(__name__)
app.secret_key = "hosteldb-secret-key"

def query_db(sql, params=(), fetch=True):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute(sql, params)
    data = cur.fetchall() if fetch else None
    if not fetch:
        db.commit()
    cur.close()
    db.close()
    return data

@app.route("/")
def dashboard():
    stats = {
        "students": query_db("SELECT COUNT(*) n FROM Students")[0]["n"],
        "hostels": query_db("SELECT COUNT(*) n FROM Hostels")[0]["n"],
        "rooms": query_db("SELECT COUNT(*) n FROM Rooms")[0]["n"],
        "available": query_db("SELECT COUNT(*) n FROM Beds WHERE Status='Available'")[0]["n"],
        "complaints": query_db("SELECT COUNT(*) n FROM Complaints WHERE Status <> 'Resolved'")[0]["n"],
        "maintenance": query_db("SELECT COUNT(*) n FROM MaintenanceRequests WHERE Status <> 'Completed'")[0]["n"],
        "payments": query_db("SELECT COUNT(*) n FROM Payments WHERE PaymentStatus='Pending'")[0]["n"]
    }
    allocations=query_db("""
        SELECT s.Name,h.HostelName,r.RoomNumber,b.BedNumber,a.AllocationDate
        FROM Allocations a
        JOIN Students s ON s.StudentID=a.StudentID
        JOIN Beds b ON b.BedID=a.BedID
        JOIN Rooms r ON r.RoomID=b.RoomID
        JOIN Hostels h ON h.HostelID=r.HostelID
        WHERE a.Status='Active'
        ORDER BY a.AllocationID DESC LIMIT 8
    """)
    return render_template("dashboard.html",stats=stats,allocations=allocations)

@app.route("/students")
def students():
    return render_template("students.html",students=query_db("SELECT * FROM Students ORDER BY StudentID DESC"))

@app.route("/students/add",methods=["GET","POST"])
def add_student():
    if request.method=="POST":
        query_db("""INSERT INTO Students
        (Name,Gender,DateOfBirth,Phone,Email,Department,YearOfStudy)
        VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (request.form["name"],request.form["gender"],request.form["dob"],request.form["phone"],
         request.form["email"],request.form["department"],request.form["year"]),False)
        flash("Student added successfully.","success")
        return redirect(url_for("students"))
    return render_template("add_student.html")

@app.route("/rooms")
def rooms():
    data=query_db("""
        SELECT r.*,h.HostelName,
        (SELECT COUNT(*) FROM Beds b WHERE b.RoomID=r.RoomID AND b.Status='Available') available_beds
        FROM Rooms r JOIN Hostels h ON h.HostelID=r.HostelID
        ORDER BY h.HostelName,r.RoomNumber
    """)
    return render_template("rooms.html",rooms=data)

@app.route("/allocations")
def allocations():
    data=query_db("""
        SELECT a.AllocationID,s.Name,h.HostelName,r.RoomNumber,b.BedNumber,
        a.AllocationDate,a.VacateDate,a.Status
        FROM Allocations a
        JOIN Students s ON s.StudentID=a.StudentID
        JOIN Beds b ON b.BedID=a.BedID
        JOIN Rooms r ON r.RoomID=b.RoomID
        JOIN Hostels h ON h.HostelID=r.HostelID
        ORDER BY a.AllocationID DESC
    """)
    return render_template("allocations.html",allocations=data)

@app.route("/allocations/add",methods=["GET","POST"])
def add_allocation():
    if request.method=="POST":
        query_db("""INSERT INTO Allocations(StudentID,BedID,AllocationDate,Status)
                    VALUES(%s,%s,%s,'Active')""",
                 (request.form["student_id"],request.form["bed_id"],request.form["allocation_date"]),False)
        query_db("UPDATE Beds SET Status='Occupied' WHERE BedID=%s",(request.form["bed_id"],),False)
        flash("Bed allocated successfully.","success")
        return redirect(url_for("allocations"))
    students=query_db("SELECT StudentID,Name FROM Students ORDER BY Name")
    beds=query_db("""SELECT b.BedID,b.BedNumber,r.RoomNumber,h.HostelName
                     FROM Beds b JOIN Rooms r ON r.RoomID=b.RoomID
                     JOIN Hostels h ON h.HostelID=r.HostelID
                     WHERE b.Status='Available'
                     ORDER BY h.HostelName,r.RoomNumber,b.BedNumber""")
    return render_template("add_allocation.html",students=students,beds=beds)

@app.route("/vacating")
def vacating():
    data=query_db("""SELECT v.VacatingID,s.Name,h.HostelName,r.RoomNumber,b.BedNumber,
                     v.VacateDate,v.Reason,v.Remarks
                     FROM VacatingRecords v
                     JOIN Students s ON s.StudentID=v.StudentID
                     JOIN Beds b ON b.BedID=v.BedID
                     JOIN Rooms r ON r.RoomID=b.RoomID
                     JOIN Hostels h ON h.HostelID=r.HostelID
                     ORDER BY v.VacateDate DESC""")
    return render_template("vacating.html",records=data)

@app.route("/vacating/add",methods=["GET","POST"])
def add_vacating():
    if request.method=="POST":
        sid=request.form["student_id"]; bid=request.form["bed_id"]; date=request.form["vacate_date"]
        query_db("""INSERT INTO VacatingRecords(StudentID,BedID,VacateDate,Reason,Remarks)
                    VALUES(%s,%s,%s,%s,%s)""",
                 (sid,bid,date,request.form["reason"],request.form["remarks"]),False)
        query_db("""UPDATE Allocations SET VacateDate=%s,Status='Vacated'
                    WHERE StudentID=%s AND BedID=%s AND Status='Active'""",(date,sid,bid),False)
        query_db("UPDATE Beds SET Status='Available' WHERE BedID=%s",(bid,),False)
        flash("Student vacated successfully.","success")
        return redirect(url_for("vacating"))
    students=query_db("SELECT StudentID,Name FROM Students ORDER BY Name")
    beds=query_db("""SELECT DISTINCT b.BedID,b.BedNumber,r.RoomNumber,h.HostelName
                     FROM Beds b JOIN Rooms r ON r.RoomID=b.RoomID
                     JOIN Hostels h ON h.HostelID=r.HostelID
                     JOIN Allocations a ON a.BedID=b.BedID AND a.Status='Active'
                     ORDER BY h.HostelName,r.RoomNumber,b.BedNumber""")
    return render_template("add_vacating.html",students=students,beds=beds)

@app.route("/payments")
def payments():
    data=query_db("""SELECT p.PaymentID,s.Name,p.Amount,p.PaymentDate,p.PaymentType,p.PaymentStatus
                     FROM Payments p JOIN Students s ON s.StudentID=p.StudentID
                     ORDER BY p.PaymentID DESC""")
    return render_template("payments.html",payments=data)

@app.route("/payments/add",methods=["GET","POST"])
def add_payment():
    if request.method=="POST":
        query_db("""INSERT INTO Payments(StudentID,Amount,PaymentDate,PaymentType,PaymentStatus)
                    VALUES(%s,%s,%s,%s,%s)""",
                 (request.form["student_id"],request.form["amount"],request.form["payment_date"],
                  request.form["payment_type"],request.form["payment_status"]),False)
        flash("Payment added successfully.","success")
        return redirect(url_for("payments"))
    return render_template("add_payment.html",students=query_db("SELECT StudentID,Name FROM Students ORDER BY Name"))

@app.route("/complaints")
def complaints():
    data=query_db("""SELECT c.ComplaintID,s.Name,c.ComplaintType,c.Description,c.ComplaintDate,c.Status
                     FROM Complaints c JOIN Students s ON s.StudentID=c.StudentID
                     ORDER BY c.ComplaintID DESC""")
    return render_template("complaints.html",complaints=data)

@app.route("/complaints/add",methods=["GET","POST"])
def add_complaint():
    if request.method=="POST":
        query_db("""INSERT INTO Complaints(StudentID,ComplaintType,Description,ComplaintDate,Status)
                    VALUES(%s,%s,%s,%s,%s)""",
                 (request.form["student_id"],request.form["complaint_type"],request.form["description"],
                  request.form["complaint_date"],request.form["status"]),False)
        flash("Complaint submitted successfully.","success")
        return redirect(url_for("complaints"))
    return render_template("add_complaint.html",students=query_db("SELECT StudentID,Name FROM Students ORDER BY Name"))

@app.route("/maintenance")
def maintenance():
    data=query_db("""SELECT m.RequestID,s.Name,h.HostelName,r.RoomNumber,m.Issue,m.Description,
                     m.RequestDate,m.Status
                     FROM MaintenanceRequests m
                     JOIN Students s ON s.StudentID=m.StudentID
                     JOIN Rooms r ON r.RoomID=m.RoomID
                     JOIN Hostels h ON h.HostelID=r.HostelID
                     ORDER BY m.RequestID DESC""")
    return render_template("maintenance.html",maintenance=data)

@app.route("/maintenance/add",methods=["GET","POST"])
def add_maintenance():
    if request.method=="POST":
        query_db("""INSERT INTO MaintenanceRequests
                    (StudentID,RoomID,Issue,Description,RequestDate,Status)
                    VALUES(%s,%s,%s,%s,%s,%s)""",
                 (request.form["student_id"],request.form["room_id"],request.form["issue"],
                  request.form["description"],request.form["request_date"],request.form["status"]),False)
        flash("Maintenance request submitted.","success")
        return redirect(url_for("maintenance"))
    students=query_db("SELECT StudentID,Name FROM Students ORDER BY Name")
    rooms=query_db("""SELECT r.RoomID,r.RoomNumber,h.HostelName FROM Rooms r
                      JOIN Hostels h ON h.HostelID=r.HostelID ORDER BY h.HostelName,r.RoomNumber""")
    return render_template("add_maintenance.html",students=students,rooms=rooms)

@app.route("/services")
def services():
    return render_template("services.html",services=query_db("SELECT * FROM Services ORDER BY ServiceID DESC"))

@app.route("/service-requests")
def service_requests():
    data=query_db("""SELECT sr.ServiceRequestID,s.Name,sv.ServiceName,sr.RequestDate,sr.Status
                     FROM ServiceRequests sr
                     JOIN Students s ON s.StudentID=sr.StudentID
                     JOIN Services sv ON sv.ServiceID=sr.ServiceID
                     ORDER BY sr.ServiceRequestID DESC""")
    return render_template("service_requests.html",requests=data)

@app.route("/staff")
def staff():
    data=query_db("""SELECT st.StaffID,st.Name,st.Role,st.Phone,h.HostelName
                     FROM Staff st LEFT JOIN Hostels h ON h.HostelID=st.HostelID
                     ORDER BY st.StaffID DESC""")
    return render_template("staff.html",staff=data)

@app.route("/visitors")
def visitors():
    data=query_db("""SELECT v.VisitorID,s.Name,v.VisitorName,v.Relationship,
                     v.VisitDate,v.EntryTime,v.ExitTime
                     FROM Visitors v JOIN Students s ON s.StudentID=v.StudentID
                     ORDER BY v.VisitDate DESC""")
    return render_template("visitors.html",visitors=data)

if __name__=="__main__":
    app.run(debug=True)
