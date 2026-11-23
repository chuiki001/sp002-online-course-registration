-- SP-002: Online Course Registration Portal (PostgreSQL 15+ Schema)
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    full_name VARCHAR(120) NOT NULL,
    email VARCHAR(150) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role VARCHAR(20) NOT NULL CHECK (role IN ('STUDENT', 'ADVISOR', 'ADMIN')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE student_profiles (
    user_id UUID PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    matric_number VARCHAR(30) UNIQUE NOT NULL,
    department VARCHAR(100) NOT NULL,
    level INT NOT NULL CHECK (level IN (100, 200, 300, 400, 500)),
    advisor_id UUID REFERENCES users(id) ON DELETE SET NULL
);

CREATE TABLE semesters (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    code VARCHAR(30) UNIQUE NOT NULL,
    status VARCHAR(20) NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN', 'ADD_DROP', 'CLOSED')),
    min_credits INT NOT NULL DEFAULT 15,
    max_credits INT NOT NULL DEFAULT 24
);

CREATE TABLE courses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    semester_id UUID NOT NULL REFERENCES semesters(id) ON DELETE CASCADE,
    code VARCHAR(15) NOT NULL,
    title VARCHAR(150) NOT NULL,
    credit_units INT NOT NULL CHECK (credit_units BETWEEN 1 AND 6),
    level INT NOT NULL,
    capacity INT NOT NULL CHECK (capacity > 0),
    enrolled_count INT NOT NULL DEFAULT 0 CHECK (enrolled_count >= 0 AND enrolled_count <= capacity),
    day_of_week VARCHAR(10) NOT NULL CHECK (day_of_week IN ('MON', 'TUE', 'WED', 'THU', 'FRI', 'SAT')),
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    UNIQUE (semester_id, code),
    CHECK (end_time > start_time)
);

CREATE TABLE course_prerequisites (
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    prerequisite_code VARCHAR(15) NOT NULL,
    PRIMARY KEY (course_id, prerequisite_code)
);

CREATE TABLE student_completed_courses (
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    course_code VARCHAR(15) NOT NULL,
    grade VARCHAR(2) NOT NULL CHECK (grade IN ('A', 'B', 'C', 'D', 'E')),
    PRIMARY KEY (student_id, course_code)
);

CREATE TABLE registrations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    student_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    semester_id UUID NOT NULL REFERENCES semesters(id) ON DELETE CASCADE,
    status VARCHAR(20) NOT NULL DEFAULT 'DRAFT' CHECK (status IN ('DRAFT', 'SUBMITTED', 'APPROVED', 'REJECTED')),
    total_credits INT NOT NULL DEFAULT 0,
    advisor_remark TEXT,
    submitted_at TIMESTAMP WITH TIME ZONE,
    UNIQUE (student_id, semester_id)
);

CREATE TABLE registration_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    registration_id UUID NOT NULL REFERENCES registrations(id) ON DELETE CASCADE,
    course_id UUID NOT NULL REFERENCES courses(id) ON DELETE CASCADE,
    is_carryover BOOLEAN NOT NULL DEFAULT FALSE,
    added_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE (registration_id, course_id)
);
