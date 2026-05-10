from app import create_app, db
from app.models import User, Department
from werkzeug.security import generate_password_hash

# Initialize the application context
app = create_app()

with app.app_context():
    print("Clearing old data and seeding new data...")
    
    # 1. Create a Department
    dept = Department(name="Engineering", description="Core Development Team")
    db.session.add(dept)
    db.session.commit() # Save to get the department ID

    # 2. Create the HR Admin User
    admin = User(
        username="hr_admin",
        email="admin@focusguard.com",
        password_hash=generate_password_hash("admin123"), # SECURE HASHING
        role="admin",
        department_id=dept.id
    )

    # 3. Create a Standard Employee User
    employee = User(
        username="john_doe",
        email="employee@focusguard.com",
        password_hash=generate_password_hash("emp123"), # SECURE HASHING
        role="employee",
        department_id=dept.id
    )

    # Add users to the database and save
    db.session.add(admin)
    db.session.add(employee)
    db.session.commit()

    print("Success! Database seeded.")
    print("Admin Email: admin@focusguard.com | Password: admin123")
    print("Employee Email: employee@focusguard.com | Password: emp123")