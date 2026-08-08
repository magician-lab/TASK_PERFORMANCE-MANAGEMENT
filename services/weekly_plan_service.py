from datetime import (
    date,
    datetime,
    timedelta
)

from sqlalchemy.orm import joinedload

from extensions import db

from models.weekly_plan import WeeklyPlan
from models.activity import Activity

from models.enums import (
    PlanStatus,
    VerificationStatus,
    ActivityStatus,
    TaskPriority
)



# =========================================================
# CURRENT WEEK
# =========================================================

def get_current_week():

    today = date.today()

    week_start = today - timedelta(
        days=today.weekday()
    )

    week_end = week_start + timedelta(
        days=6
    )

    return week_start, week_end



# =========================================================
# EMPLOYEE DASHBOARD
# =========================================================

def get_employee_weekly_dashboard(user):

    today = date.today()

    current_plan = WeeklyPlan.query.filter(

        WeeklyPlan.employee_id == user.id,

        WeeklyPlan.week_start <= today,

        WeeklyPlan.week_end >= today

    ).first()


    previous_plans = WeeklyPlan.query.filter(

        WeeklyPlan.employee_id == user.id,

        WeeklyPlan.week_end < today

    ).order_by(

        WeeklyPlan.week_start.desc()

    ).all()



    return {

        "current_plan": current_plan,

        "previous_plans": previous_plans,


        "total_plans":

            WeeklyPlan.query.filter_by(
                employee_id=user.id
            ).count(),


        "submitted_plans":

            WeeklyPlan.query.filter(

                WeeklyPlan.employee_id == user.id,

                WeeklyPlan.status == PlanStatus.SUBMITTED

            ).count(),


        "active_plans":

            WeeklyPlan.query.filter(

                WeeklyPlan.employee_id == user.id,

                WeeklyPlan.status == PlanStatus.ACTIVE

            ).count(),


        "completed_plans":

            WeeklyPlan.query.filter(

                WeeklyPlan.employee_id == user.id,

                WeeklyPlan.status == PlanStatus.COMPLETED

            ).count()

    }



# =========================================================
# CHECK EXISTING PLAN
# =========================================================

def week_plan_exists(employee_id):


    week_start, week_end = get_current_week()


    return WeeklyPlan.query.filter(

        WeeklyPlan.employee_id == employee_id,

        WeeklyPlan.week_start == week_start,

        WeeklyPlan.week_end == week_end

    ).first()



# =========================================================
# GET PLAN
# =========================================================


def get_weekly_plan(plan_id):


    return WeeklyPlan.query.options(

        joinedload(
            WeeklyPlan.activities
        ),

        joinedload(
            WeeklyPlan.employee
        )

    ).get_or_404(plan_id)




# =========================================================
# CREATE WEEKLY PLAN
# =========================================================


def create_weekly_plan(

    employee,

    objectives,

    notes,

    activities

):


    existing = week_plan_exists(
        employee.id
    )


    if existing:

        return (

            False,

            "You already have a plan for this week.",

            existing

        )



    week_start, week_end = get_current_week()



    plan = WeeklyPlan(

        employee_id=employee.id,


        # FIXED
        employee_number=employee.employee_number,


        week_number=
            week_start.isocalendar().week,


        year=
            week_start.year,


        week_start=week_start,


        week_end=week_end,


        objectives=objectives,


        notes=notes,


        status=PlanStatus.DRAFT,


        total_activities=0,


        created_at=datetime.utcnow()

    )


    try:


        db.session.add(plan)


        db.session.flush()



        activity_count = 0



        for item in activities:



            if not item.get("title"):

                continue



            activity_date = None



            if item.get("activity_date"):


                activity_date = datetime.strptime(

                    item["activity_date"],

                    "%Y-%m-%d"

                ).date()



            priority = item.get(
                "priority",
                "NORMAL"
            )



            try:

                priority = TaskPriority[
                    priority
                ]

            except:

                priority = TaskPriority.NORMAL




            activity = Activity(


                plan_id=plan.id,


                employee_number=
                    employee.employee_number,


                title=item["title"],


                description=
                    item.get(
                        "description"
                    ),


                activity_date=activity_date,


                priority=priority,


                employee_status=
                    ActivityStatus.PENDING,


                verification_status=
                    VerificationStatus.PENDING

            )



            db.session.add(activity)


            activity_count += 1



        plan.total_activities = activity_count


        db.session.commit()



        return (

            True,

            "Weekly plan created successfully.",

            plan

        )


    except Exception as e:


        db.session.rollback()


        return (

            False,

            str(e),

            None

        )




# =========================================================
# UPDATE PLAN
# =========================================================


def update_weekly_plan(

    plan,

    objectives,

    notes,

    activities

):


    try:


        plan.objectives = objectives

        plan.notes = notes

        plan.updated_at = datetime.utcnow()



        existing_ids = {

            activity.id

            for activity in plan.activities

        }



        submitted_ids=set()



        for item in activities:



            activity_id=item.get("id")



            activity_date=None



            if item.get("activity_date"):


                activity_date=datetime.strptime(

                    item["activity_date"],

                    "%Y-%m-%d"

                ).date()



            if activity_id:



                activity=Activity.query.get(

                    int(activity_id)

                )


                if activity:


                    activity.title=item["title"]

                    activity.description=item.get(
                        "description"
                    )

                    activity.activity_date=activity_date


                    submitted_ids.add(
                        activity.id
                    )



            else:



                activity=Activity(


                    plan_id=plan.id,


                    employee_number=
                        plan.employee_number,


                    title=item["title"],


                    description=item.get(
                        "description"
                    ),


                    activity_date=activity_date,


                    priority=
                        TaskPriority.NORMAL,


                    employee_status=
                        ActivityStatus.PENDING,


                    verification_status=
                        VerificationStatus.PENDING

                )

                db.session.add(activity)



        delete_ids = existing_ids - submitted_ids



        if delete_ids:


            Activity.query.filter(

                Activity.id.in_(delete_ids)

            ).delete(

                synchronize_session=False

            )



        plan.total_activities=len(
            plan.activities
        )


        db.session.commit()



        return True,"Weekly plan updated successfully."



    except Exception as e:


        db.session.rollback()


        return False,str(e)





# =========================================================
# SUBMIT PLAN
# =========================================================


def submit_weekly_plan(plan):


    if plan.submitted:


        return False,"Already submitted."



    if len(plan.activities)==0:


        return False,"Add activities first."



    plan.submitted=True


    plan.submitted_at=datetime.utcnow()


    plan.status=PlanStatus.SUBMITTED



    db.session.commit()



    return True,"Weekly plan submitted successfully."





# =========================================================
# HISTORY
# =========================================================


def get_plan_history(employee_id):


    return WeeklyPlan.query.filter_by(

        employee_id=employee_id

    ).order_by(

        WeeklyPlan.week_start.desc()

    ).all()