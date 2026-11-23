from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CourseSlot:
    code: str
    credit_units: int
    day_of_week: str
    start_minutes: int
    end_minutes: int
    capacity: int
    enrolled_count: int
    prerequisites: tuple[str, ...]
    is_carryover: bool = False  # Added in Week 12 CR-01


@dataclass(frozen=True)
class ValidationContext:
    selected_courses: list[CourseSlot]
    passed_course_codes: set[str]
    min_credits: int = 15
    max_credits: int = 24
    allow_late_add_drop: bool = False  # Added in Week 12 CR-01


class RegistrationRuleStrategy(Protocol):
    def validate(self, ctx: ValidationContext) -> list[str]:
        ...


class CreditLimitRule:
    def validate(self, ctx: ValidationContext) -> list[str]:
        total = sum(c.credit_units for c in ctx.selected_courses)
        errors: list[str] = []
        if total < ctx.min_credits:
            errors.append(f"Total credits ({total} CU) is below minimum required ({ctx.min_credits} CU).")
        if total > ctx.max_credits:
            errors.append(f"Total credits ({total} CU) exceeds maximum allowed ({ctx.max_credits} CU).")
        return errors


class PrerequisiteRule:
    def validate(self, ctx: ValidationContext) -> list[str]:
        errors: list[str] = []
        for course in ctx.selected_courses:
            missing = [p for p in course.prerequisites if p not in ctx.passed_course_codes]
            if missing:
                errors.append(f"{course.code} requires passed prerequisite(s): {', '.join(missing)}.")
        return errors


class TimetableClashRule:
    def validate(self, ctx: ValidationContext) -> list[str]:
        errors: list[str] = []
        courses = ctx.selected_courses
        for i in range(len(courses)):
            for j in range(i + 1, len(courses)):
                a, b = courses[i], courses[j]
                if a.day_of_week == b.day_of_week:
                    if a.start_minutes < b.end_minutes and b.start_minutes < a.end_minutes:
                        errors.append(
                            f"Timetable clash on {a.day_of_week}: {a.code} overlaps with {b.code}."
                        )
        return errors


class SeatCapacityRule:
    def validate(self, ctx: ValidationContext) -> list[str]:
        errors: list[str] = []
        for course in ctx.selected_courses:
            if course.enrolled_count >= course.capacity:
                errors.append(f"{course.code} has reached full capacity ({course.capacity}/{course.capacity}).")
        return errors


class CompositeRegistrationValidator:
    def __init__(self, rules: list[RegistrationRuleStrategy]) -> None:
        self._rules = rules

    def validate_all(self, ctx: ValidationContext) -> list[str]:
        violations: list[str] = []
        for rule in self._rules:
            violations.extend(rule.validate(ctx))
        return violations


def build_default_validator(enforce_credit_bounds: bool = True) -> CompositeRegistrationValidator:
    rules: list[RegistrationRuleStrategy] = [
        PrerequisiteRule(),
        TimetableClashRule(),
        SeatCapacityRule(),
    ]
    if enforce_credit_bounds:
        rules.insert(0, CreditLimitRule())
    return CompositeRegistrationValidator(rules)
