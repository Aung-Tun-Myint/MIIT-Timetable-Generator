import pandas as pd
import numpy as np
import random
from deap import base, creator, tools, algorithms
from collections import defaultdict
import textwrap
import time, os

def generate_timetables(instructors_courses_path, backlog_path, elective_path, output_folder, progress):
    # Load data
    instructors_courses_df = pd.read_csv(instructors_courses_path)
    backlog_students_df = pd.read_csv(backlog_path)
    elective_students_df = pd.read_csv(elective_path)
    # Define time slots and days
    days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
    times = ['9:00', '10:00', '11:00', '13:00', '14:00', '15:00', '16:00']
    # reserved_slots = [('Monday', '9:00'), ('Friday', '9:00')]

    # Create time slot indices
    all_time_slots = [(day, time) for day in days for time in times]
    time_slot_indices = {i: slot for i, slot in enumerate(all_time_slots)}
    num_time_slots = len(all_time_slots)

    # Create mappings for time slots
    time_slots_by_day_time = defaultdict(dict)
    for idx, (day, time) in time_slot_indices.items():
        time_slots_by_day_time[day][time] = idx

    # Process courses
    # Process courses
    course_sessions = []
    for idx, row in instructors_courses_df.iterrows():
        batch = row['Batch'].strip()
        course_number = row['Course Number'].strip()
        course_name = row['Course Name'].strip()
        program = row['Program'].strip()
        instructor = row['Instructor-in-Charge'].strip()
        section = row['Section Number'].strip() if not pd.isna(row['Section Number']) else ''
        lecture_hours = int(row['Lecture Hours']) if not pd.isna(row['Lecture Hours']) else 0
        lab_hours = int(row['Lab Hours']) if not pd.isna(row['Lab Hours']) else 0
        room = str(row['ROOM']).strip() if not pd.isna(row['ROOM']) else None
        combined_program = str(row['CombinedProgram']).strip().lower() == 'true'
        combined_section = str(row['CombinedSection']).strip().lower() == 'true'

        # Rest of the code remains the same...

        # Unique course ID including program and section
        course_id = f"{course_number}_{program}_{section}" if section else f"{course_number}_{program}"

        # Total sessions needed
        lecture_sessions = lecture_hours
        lab_sessions = lab_hours // 2  # Assuming labs are 2-hour sessions

        # Create lecture sessions
        for session_num in range(lecture_sessions):
            session_id = f"{course_id}_L{session_num}"
            course_sessions.append({
                'course_id': course_id,
                'session_id': session_id,
                'batch': batch,
                'name': course_name,
                'program': program,
                'instructor': instructor,
                'is_lab': False,
                'room': room,
                'section': section,
                'duration': 1,  # 1-hour lectures
                'combined_program': combined_program,
                'combined_section': combined_section,
            })

        # Create lab sessions
        for session_num in range(lab_sessions):
            session_id = f"{course_id}_Lab{session_num}"
            course_sessions.append({
                'course_id': course_id,
                'session_id': session_id,
                'batch': batch,
                'name': course_name,
                'program': program,
                'instructor': instructor,
                'is_lab': True,
                'room': room,
                'section': section,
                'duration': 2,  # 2-hour labs
                'combined_program': combined_program,
                'combined_section': combined_section,
            })

    # Process students
    student_courses = {}
    # Backlog students
    for idx, row in backlog_students_df.iterrows():
        roll_number = row['RollNumber']
        student_courses[roll_number] = set()
        for course in course_sessions:
            course_col = course['course_id'].split('_')[0]
            program = course['program']
            if course_col in row and row[course_col] == 1.0:
                if program in roll_number.upper():
                    student_courses[roll_number].add(course['session_id'])
    # Elective students
    for idx, row in elective_students_df.iterrows():
        roll_number = row['RollNumber']
        if roll_number not in student_courses:
            student_courses[roll_number] = set()
        for course in course_sessions:
            course_col = course['course_id'].split('_')[0]
            program = course['program']
            if course_col in row and row[course_col] == 1.0:
                if program in roll_number.upper():
                    student_courses[roll_number].add(course['session_id'])

    course_students = defaultdict(set)
    for student, courses in student_courses.items():
        for course_id in courses:
            course_students[course_id].add(student)


    # Populate batch_students with regular students only
    batch_students = defaultdict(list)
    # Assume student IDs are of the format 'YYYY-MIIT-PROGRAM-XXX'
    for batch_year in range(2016, 2023):  # Adjust years as needed
        for program in ['CSE', 'ECE']:
            num_students = 2
            if batch_year == 2021 and program == 'CSE':
                num_students = 4
            if batch_year == 2021 and program == 'ECE':
                continue  # No ECE students in 2021
            for section in ['', 'Section 1', 'Section 2']:
                batch_key = (f'BE-{batch_year}', program, section)
                for student_num in range(1, num_students + 1):
                    student_id = f'{batch_year}-MIIT-{program}-{str(student_num).zfill(3)}'
                    if student_id not in student_courses:  # Exclude elective and backlog students
                        # Assign students to sections for 2021 batch
                        if batch_year == 2021 and program == 'CSE':
                            if section == 'Section 1' and student_num <= 2:
                                batch_students[batch_key].append(student_id)
                            elif section == 'Section 2' and student_num > 2:
                                batch_students[batch_key].append(student_id)
                        else:
                            if section == '':
                                batch_students[batch_key].append(student_id)

    # ... (rest of your timetable generation code)

    creator.create("FitnessMin", base.Fitness, weights=(-1.0,))
    creator.create("Individual", list, fitness=creator.FitnessMin)

    toolbox = base.Toolbox()

    # Attribute generator: Randomly assign time slot indices to each session
    def create_individual():
        individual = []
        for session in course_sessions:
            if session['is_lab']:
                # Only consider valid lab starting slots (15:00)
                lab_start_slots = [idx for idx, (day, time) in time_slot_indices.items() if time == '15:00']
                individual.append(random.choice(lab_start_slots))
            else:
                individual.append(random.randint(0, num_time_slots - 1))
        return individual

    toolbox.register("individual", tools.initIterate, creator.Individual, create_individual)
    toolbox.register("population", tools.initRepeat, list, toolbox.individual)

    # Fitness function remains the same
    def evaluate(individual):
        penalty = 0
        schedule = {}
        instructor_schedule = defaultdict(lambda: defaultdict(set))
        room_schedule = defaultdict(lambda: defaultdict(set))
        student_schedule = defaultdict(lambda: defaultdict(set))
        course_days = defaultdict(set)

        # Initialize penalty counters
        penalty_counters = {
            'invalid_time_slot': 0,
            'lab_scheduling': 0,
            'instructor_conflicts': 0,
            'room_conflicts': 0,
            'student_conflicts': 0,
            'multiple_sessions_same_day': 0,
            'missing_sessions': 0
        }
        for idx, session_time_slot_idx in enumerate(individual):
            session = course_sessions[idx]
            session_id = session['session_id']
            course_id = session['course_id']
            if session_time_slot_idx >= num_time_slots:
                penalty += 20  # Reduced from 50
                penalty_counters['invalid_time_slot'] += 1
                continue

            time_slot = time_slot_indices[session_time_slot_idx]
            day, time = time_slot
            duration = session['duration']
            program = session['program']

            # For labs, ensure the next time slot is also available
            if session['is_lab']:
                if time != '15:00':
                    penalty += 10  # Reduced from 20
                    penalty_counters['lab_scheduling'] += 1
                    continue
                # Check if the next time slot (16:00) is available
                next_time_slot_idx = session_time_slot_idx + 1
                if next_time_slot_idx >= num_time_slots or time_slot_indices[next_time_slot_idx][0] != day or time_slot_indices[next_time_slot_idx][1] != '16:00':
                    penalty += 10  # Reduced from 20
                    penalty_counters['lab_scheduling'] += 1
                time_slots = [time, '16:00']
            else:
                time_slots = [time]

            schedule[session_id] = (day, time_slots)

            # Instructor conflicts
            instructor = session['instructor']
            for t in time_slots:
                if t in instructor_schedule[instructor][day]:
                    penalty += 5  # Reduced from 10
                    penalty_counters['instructor_conflicts'] += 1
                instructor_schedule[instructor][day].add(t)

            # Room conflicts
            room = session['room']
            if room:
                for t in time_slots:
                    if t in room_schedule[room][day]:
                        penalty += 2  # Reduced from 5
                        penalty_counters['room_conflicts'] += 1
                    room_schedule[room][day].add(t)

            # Student conflicts
            # For batch students
            batch = session['batch']
            section = session['section']
            key = (batch, program, section)
            students_in_batch = batch_students.get(key, [])
            combined_program = session.get('combined_program', False)
            combined_section = session.get('combined_section', False)

            # If the program is 'CSE and ECE', include students from both programs
            if combined_section:
                key_section1 = (batch, program, 'Section 1')
                key_section2 = (batch, program, 'Section 2')
                students_in_batch = batch_students.get(key_section1, []) + batch_students.get(key_section2, [])

            elif combined_program:
                key_cse = (batch, 'CSE', section)
                key_ece = (batch, 'ECE', section)
                students_in_batch = batch_students.get(key_cse, []) + batch_students.get(key_ece, [])

            for student in students_in_batch:
                for t in time_slots:
                    if t in student_schedule[student][day]:
                        penalty += 5  # Reduced from 10
                        penalty_counters['student_conflicts'] += 1
                    student_schedule[student][day].add(t)

            # Conflict checking for elective and backlog students
            # Get the set of students enrolled in this session
            students_in_course = course_students.get(session_id, set())

            for student in students_in_course:
                for t in time_slots:
                    if t in student_schedule[student][day]:
                        penalty += 5  # Adjusted penalty
                        penalty_counters['student_conflicts'] += 1
                    student_schedule[student][day].add(t)

            # For elective and backlog students
            # for student, student_session_list in student_courses.items():
            #
            #     if session_id in student_session_list:
            #         for t in time_slots:
            #             if t in student_schedule[student][day]:
            #                 penalty += 5  # Reduced from 10
            #                 penalty_counters['student_conflicts'] += 1
            #             student_schedule[student][day].add(t)

            # Avoid scheduling multiple sessions of the same course on the same day
            if day in course_days[course_id]:
                penalty += 1  # Reduced from 2
                penalty_counters['multiple_sessions_same_day'] += 1
            course_days[course_id].add(day)

        # Ensure all sessions are scheduled
        # Missing sessions
        missing_sessions = len(course_sessions) - len(schedule)
        if missing_sessions > 0:
            penalty += missing_sessions * 20  # Reduced from 50
            penalty_counters['missing_sessions'] += missing_sessions

        # Store penalty breakdown for analysis
        individual.penalty_counters = penalty_counters
        return (penalty,)


    toolbox.register("evaluate", evaluate)
    toolbox.register("mate", tools.cxUniform, indpb=0.7)
    toolbox.register("mutate", tools.mutUniformInt, low=0, up=num_time_slots - 1, indpb=0.2)
    toolbox.register("select", tools.selTournament, tournsize=3)

    # Genetic Algorithm parameters
    population_size = 1000
    num_generations = 100
    crossover_prob = 0.9
    mutation_prob = 0.3

    # Create initial population
    pop = toolbox.population(n=population_size)

    # Statistics
    stats = tools.Statistics(lambda ind: ind.fitness.values)
    stats.register("avg", np.mean)
    stats.register("min", np.min)
    stats.register("max", np.max)

    # Initialize cumulative penalty counters
    cumulative_penalties = {
        'invalid_time_slot': 0,
        'lab_scheduling': 0,
        'instructor_conflicts': 0,
        'room_conflicts': 0,
        'student_conflicts': 0,
        'multiple_sessions_same_day': 0,
        'missing_sessions': 0
    }

    # Throughout your code, update the progress dictionary
    # For example:
    progress['message'] = 'Initializing genetic algorithm...'
    progress['percentage'] = 10

    NELITISTS = int(0.05 * population_size)
    # After each generation, update the progress
    for gen in range(num_generations):
        # ... existing code ...
        offspring = algorithms.varAnd(pop, toolbox, cxpb=crossover_prob, mutpb=mutation_prob)
        fits = toolbox.map(toolbox.evaluate, offspring)
        for fit, ind in zip(fits, offspring):
            ind.fitness.values = fit

        # Combine population and offspring for elitism
        combined_population = pop + offspring
        # Evaluate individuals before accessing penalty_counters
        for ind in combined_population:
            if not hasattr(ind, 'penalty_counters'):
                ind.penalty_counters = {}  # Ensure all individuals have the penalty_counters attribute

        # Aggregate penalty data
        for ind in combined_population:
            for key in cumulative_penalties.keys():
                cumulative_penalties[key] += ind.penalty_counters.get(key, 0)

        # Select the next generation population
        pop = tools.selBest(combined_population, k=population_size - NELITISTS)
        elite = tools.selBest(combined_population, k=NELITISTS)
        pop.extend(elite)


        record = stats.compile(pop)
        print(f"Generation {gen + 1}: {record}")
        print("Penalty Contributions:")
        for key, value in cumulative_penalties.items():
            print(f"  {key}: {value}")

        # Reset cumulative penalties for the next generation
        cumulative_penalties = dict.fromkeys(cumulative_penalties, 0)

        # Early stopping if an acceptable solution is found
        if record['min'] == 0:
            print("Optimal solution found.")
            break

        # Update progress
        progress['message'] = f'Generation {gen + 1} completed.'
        progress['percentage'] = int(((gen + 1) / num_generations) * 80) + 10  # Adjust percentage calculation as needed

    # Get the best individual
    best_individual = tools.selBest(pop, k=1)[0]

    print("Best Individual Penalty Breakdown:")
    for key, value in best_individual.penalty_counters.items():
        print(f"  {key}: {value}")


    best_schedule = {}

    for idx, session in enumerate(course_sessions):
        session_id = session['session_id']
        if idx >= len(best_individual):
            continue
        time_slot_idx = best_individual[idx]
        if time_slot_idx >= num_time_slots:
            continue
        time_slot = time_slot_indices[time_slot_idx]
        day, time = time_slot
        duration = session['duration']
        if session['is_lab']:
            time_slots = [time, '16:00']
        else:
            time_slots = [time]
        best_schedule[session_id] = (day, time_slots)

    # Generate timetables
    # Timetables for batches, instructors, and now students
    batch_timetables = defaultdict(list)
    instructor_timetables = defaultdict(list)
    student_timetables = defaultdict(list)

    for session in course_sessions:
        session_id = session['session_id']
        if session_id in best_schedule:
            day, time_slots = best_schedule[session_id]
            course = session
            batch = course['batch']
            program = course['program']
            section = course['section']
            key = (batch, program, section)
            # Add to batch timetables
            batch_timetables[key].append({
                'course_id': session['course_id'],
                'session_id': session_id,
                'course_name': course['name'],
                'instructor': course['instructor'],
                'day': day,
                'times': time_slots,
                'room': course['room']
            })
            # Add to instructor timetables
            instructor = course['instructor']
            instructor_timetables[instructor].append({
                'course_id': session['course_id'],
                'session_id': session_id,
                'course_name': course['name'],
                'batch': course['batch'],
                'program': course['program'],
                'section': course['section'],
                'day': day,
                'times': time_slots,
                'room': course['room']
            })
            # Add to student timetables (for elective and backlog students)
            for student, student_session_list in student_courses.items():
                if session_id in student_session_list:
                    student_timetables[student].append({
                        'course_id': session['course_id'],
                        'session_id': session_id,
                        'course_name': course['name'],
                        'instructor': course['instructor'],
                        'day': day,
                        'times': time_slots,
                        'room': course['room']
                    })


    # After completion
    progress['message'] = 'Writing timetables to Excel files...'
    progress['percentage'] = 95

    # Write timetables to Excel files in the output_folder
    # Adjust your code to save files in the specified output_folder
    # Function to create a timetable grid
    def create_timetable(schedule_entries):
        df = pd.DataFrame('', index=times, columns=days)
        for entry in schedule_entries:
            day = entry['day']
            for time in entry['times']:
                content = f"{entry['course_id']}\n{entry['course_name']}\n{entry['room']}"
                existing = df.at[time, day]
                if existing:
                    df.at[time, day] = existing + "\n" + content
                else:
                    df.at[time, day] = content
        # Apply text wrapping
        df = df.apply(lambda col: col.apply(lambda x: "\n".join(textwrap.wrap(x, width=30)) if x else x))
        return df
    # Example:
    batch_timetable_path = os.path.join(output_folder, 'Batch_Timetables.xlsx')
    instructor_timetable_path = os.path.join(output_folder, 'Instructor_Timetables.xlsx')
    student_timetable_path = os.path.join(output_folder, 'Elective_Backlog_Timetables.xlsx')


    # Write timetables to Excel files
    with pd.ExcelWriter(batch_timetable_path, engine='xlsxwriter') as writer:
        for key, schedule in batch_timetables.items():
            batch, program, section = key
            section_str = f"_Section_{section}" if section else ""
            sheet_name = f"{batch}_{program}{section_str}"
            sheet_name = sheet_name[:31]  # Sheet names can't be longer than 31 characters
            df = create_timetable(schedule)
            df.to_excel(writer, sheet_name=sheet_name)
            # Get the xlsxwriter workbook and worksheet objects.
            workbook  = writer.book
            worksheet = writer.sheets[sheet_name]
            # Adjust the column widths.
            worksheet.set_column('A:H', 20)
            # Set the format for wrapping text.
            wrap_format = workbook.add_format({'text_wrap': True, 'align': 'center', 'valign': 'vcenter'})
            worksheet.set_column('A:H', 20, wrap_format)
            worksheet.set_row(0, None, wrap_format)
            for idx in range(len(df)):
                worksheet.set_row(idx + 1, 60, wrap_format)  # Adjust row height

    with pd.ExcelWriter(instructor_timetable_path, engine='xlsxwriter') as writer:
        for instructor, schedule in instructor_timetables.items():
            sheet_name = instructor[:31]  # Sheet names can't be longer than 31 characters
            df = create_timetable(schedule)
            df.to_excel(writer, sheet_name=sheet_name)
            # Get the xlsxwriter workbook and worksheet objects.
            workbook  = writer.book
            worksheet = writer.sheets[sheet_name]
            # Adjust the column widths.
            worksheet.set_column('A:H', 20)
            # Set the format for wrapping text.
            wrap_format = workbook.add_format({'text_wrap': True, 'align': 'center', 'valign': 'vcenter'})
            worksheet.set_column('A:H', 20, wrap_format)
            worksheet.set_row(0, None, wrap_format)
            for idx in range(len(df)):
                worksheet.set_row(idx + 1, 60, wrap_format)  # Adjust row height

    # Write timetables for elective and backlog students
    with pd.ExcelWriter(student_timetable_path, engine='xlsxwriter') as writer:
        for student, schedule in student_timetables.items():
            sheet_name = student[:31]  # Sheet names can't be longer than 31 characters
            # Ensure sheet names are unique
            if sheet_name in writer.sheets:
                sheet_name = f"{sheet_name}_{random.randint(0, 9999)}"
            df = create_timetable(schedule)
            df.to_excel(writer, sheet_name=sheet_name)
            # Get the xlsxwriter workbook and worksheet objects.
            workbook  = writer.book
            worksheet = writer.sheets[sheet_name]
            # Adjust the column widths.
            worksheet.set_column('A:H', 20)
            # Set the format for wrapping text.
            wrap_format = workbook.add_format({'text_wrap': True, 'align': 'center', 'valign': 'vcenter'})
            worksheet.set_column('A:H', 20, wrap_format)
            worksheet.set_row(0, None, wrap_format)
            for idx in range(len(df)):
                worksheet.set_row(idx + 1, 60, wrap_format)  # Adjust row height

    print("Timetables have been written to 'Batch_Timetables.xlsx', 'Instructor_Timetables.xlsx', and 'Elective_Backlog_Timetables.xlsx'.")

    progress['message'] = 'Timetable generation completed.'
    progress['percentage'] = 100
