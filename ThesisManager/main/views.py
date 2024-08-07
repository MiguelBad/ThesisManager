import random
import copy
from django.shortcuts import render
from django.core.paginator import Paginator
from django.contrib.auth.decorators import login_required
from django.db.models import ProtectedError, Q
from django.shortcuts import redirect
from .models import Thesis, ThesisRequestAdd, ThesisRequestModify, ThesisRequestDelete, GroupApplication, GroupApplicationAccepted, Course, Campus, Category, Supervisor
from .forms import ThesisForm, ThesisRequestFormAdd, ThesisRequestFormModify, ThesisRequestFormDelete, CampusForm, CategoryForm, CourseForm, SupervisorForm, GroupApplicationForm
from .decorators import account_type_required
from users.models import CustomUser


def truncate_description(thesis):
    new_description = {}

    for item in thesis:
        # truncates words longer than 250 characters
        # i.e. only shows 250 character of the  thesis description
        description = item.description
        word_count = description.split()
        if len(description) > 230:
            description = ''.join(description[:230])

            punctuation = ['.', ',', '/', ';', ':', ' ']
            if description[-1] in punctuation:
                description = description[:-1] + '...'
            else:
                description = description + '...'

            new_description[item.topic_number] = description

        else:
            new_description[item.topic_number] = description

    return new_description


def paginator(request, thesis):
    # gets the thesis per page. default value = 5
    items_per_page = int(request.GET.get('items_per_page', 5))

    # use built-in tool of django for paginating the theses
    page = Paginator(thesis, items_per_page)
    page_number = request.GET.get("page")
    page_obj = page.get_page(page_number)

    # values used to show the number of items shown and total number of theses
    total_pages = range(1, page.num_pages + 1)
    start_num = (page_obj.number - 1) * items_per_page + 1
    end_num = min(start_num + items_per_page - 1, page_obj.paginator.count)
    total_theses = len(thesis)

    return page_obj, total_pages, start_num, end_num, total_pages, items_per_page, total_theses


def changed_data_check(thesis, old_thesis_data, old_campus_list, old_course_list):
    # Checks the changes made on the values of thesis
    entries = ['topic_number', 'title', 'description', 'category_id', 'supervisor_id', 'group_taker_limit']
    thesis_dict = {}
    for key, value in vars(thesis).items():
        if key in entries:
            thesis_dict[key] = value

    old_thesis_dict = {}
    for key, value in vars(old_thesis_data).items():
        if key in entries:
            old_thesis_dict[key] = value

    changed_data = {}
    for key, value in thesis_dict.items():
        if thesis_dict[key] != old_thesis_dict[key]:
            changed_data[key] = True

    new_campus_list = [campus for campus in thesis.campus.all()]
    if new_campus_list != old_campus_list:
        changed_data['campus'] = True

    new_course_list = [course for course in thesis.course.all()]
    if new_course_list != old_course_list:
        changed_data['course'] = True
    print(changed_data)
    return changed_data


def home(request):
    theses = Thesis.objects.all()

    available_thesis = len(theses)
    available_supervisor = []

    for thesis in theses:
        available_supervisor.append(thesis.supervisor)

    context = {
        'available_thesis': available_thesis,
        'available_supervisor': len(set(available_supervisor))
    }

    return render(request, 'main/home.html', context)


def about_us(request):
    students = [
        {'name': 'Kye James Johnstone', 'number': 'S365934'},
        {'name': 'Juan Miguel Badayos', 'number': 'S365958'},
        {'name': 'Mark Joshua Tayco', 'number': 'S368036'},
        {'name': 'Agnes Juliana Javier', 'number': 'S364240'},
    ]

    context = {
        'students': students
    }

    return render(request, "main/about_us.html", context)


def thesis_details(request, topic_number):
    theses = Thesis.objects.all()

    current_thesis = None

    for thesis in theses:
        if thesis.topic_number == topic_number:
            current_thesis = thesis
            break

    if current_thesis is None:
        error_message = f"Invalid thesis number. Topic number: {topic_number} does not exist."
        # 2 Thesis title are generated under see other thesis
        random_theses = random.sample(list(theses), min(3, len(list(theses))))
        context = {
            'error_message': error_message,
            'random_theses': random_theses
        }

        return render(request, 'main/thesis_details.html', context)

    remaining_theses = [thesis for thesis in theses if thesis.topic_number != topic_number]

    random_theses = random.sample(remaining_theses, min(2, len(remaining_theses)))
    thesis_accepted_exists = False
    thesis_application_exists = False

    accepted_application_count = GroupApplicationAccepted.objects.filter(thesis__topic_number=topic_number, status='accepted').count()
    group_limit = current_thesis.group_taker_limit

    max_reached = False
    if accepted_application_count == group_limit:
        max_reached = True

    if request.user.is_authenticated:
        thesis_accepted = GroupApplicationAccepted.objects.filter(group=request.user, status='accepted')
        if thesis_accepted:
            thesis_accepted_exists = True
        else:
            thesis_accepted_exists = False

        thesis_application = GroupApplication.objects.filter(group=request.user, thesis__topic_number=topic_number)
        if thesis_application:
            thesis_application_exists = True
        else:
            thesis_application_exists = False

    if request.method == 'POST':
        thesis_data = Thesis.objects.get(topic_number=topic_number)
        current_student = request.user

        application_data = {
            'thesis': thesis_data,
            'group': current_student,
            'status': 'pending',
        }

        form = GroupApplicationForm(application_data)
        if form.is_valid():
            form.save()

            context = {
                'thesis': current_thesis,
                'random_theses': random_theses,
                'successfully_applied': True,
                'group_limit': group_limit,
                'form': form,
                'accepted_application_count': accepted_application_count,
            }

            return render(request, 'main/thesis_details.html', context)

        else:
            try:
                application_exists_data = GroupApplication.objects.get(thesis__topic_number=topic_number, group=current_student)
                application_exists = True
            except GroupApplication.DoesNotExist:
                application_exists = False

            context = {
                'thesis': current_thesis,
                'random_theses': random_theses,
                'successfully_applied': False,
                'form': form,
                'application_exists': application_exists,
                'group_limit': group_limit,
                'accepted_application_count': accepted_application_count,
            }

            return render(request, 'main/thesis_details.html', context)
    context = {
        'thesis': current_thesis,
        'random_theses': random_theses,
        'thesis_accepted_exists': thesis_accepted_exists,
        'thesis_application_exists': thesis_application_exists,
        'max_reached': max_reached,
        'accepted_application_count': accepted_application_count,
        'group_limit': group_limit,
    }

    return render(request, 'main/thesis_details.html', context)


def thesis_list(request):
    theses = Thesis.objects.all()

    # created a separate list for different filter categories
    supervisor_list = []
    campus_list = []
    course_list = []
    category_list = []

    for thesis in theses:
        # appends each category in the list
        campus_list_specific = []
        course_list_specific = []
        supervisor_list.append(thesis.supervisor)
        for campus in thesis.campus.all():
            campus_list_specific.append(campus)
        campus_list.append(campus_list_specific)
        for course in thesis.course.all():
            course_list_specific.append(course)
        course_list.append(course_list_specific)
        category_list.append(thesis.category)

    new_description = truncate_description(theses)

    # extraccts the specific names e.g. <Campus: External> will extract External
    supervisor_names = [supervisor.supervisor for supervisor in supervisor_list]
    campus_names = [campus.campus for sublist in campus_list for campus in sublist]
    course_names = [course.course for sublist in course_list for course in sublist]
    category_names = [category.category for category in category_list]

    # add the number of thesis with a the filter tag
    supervisor_count = {}
    campus_count = {}
    course_count = {}
    category_count = {}
    for supervisor in sorted(list(set(supervisor_names))):
        supervisor_count[supervisor] = supervisor_names.count(supervisor)
    for campus in sorted(list(set(campus_names))):
        campus_count[campus] = campus_names.count(campus)
    for course in sorted(list(set(course_names))):
        course_count[course] = course_names.count(course)
    for category in sorted(list(set(category_names))):
        category_count[category] = category_names.count(category)

    # retrieves the value of supervisor, campus, and coure when users interacts with filter
    # updates theses shown depending on the value set by the user
    selected_supervisor = request.GET.getlist('supervisor')
    selected_campus = request.GET.getlist('campus')
    selected_course = request.GET.getlist('course')
    selected_category = request.GET.getlist('category')
    filter_supervisor = filter_campus = filter_course = filter_category = ''

    user_filters = {
        'supervisor': selected_supervisor,
        'campus': selected_campus,
        'course': selected_course,
        'category': selected_category,
    }

    filter_query = Q()

    for filter_key, filter_value in user_filters.items():
        if filter_value:
            filter_query &= Q(**{f"{filter_key}__in": filter_value})

    theses = Thesis.objects.filter(filter_query)

    no_thesis = False
    if not theses:
        no_thesis = True

    if selected_supervisor:
        '''
            changes the url of the page to filter the list
            this fixes the issue where the the filter thesis is not stored
            in the paginator, causing the filter to reset when user
            goes to the next/previous page 
        '''
        filter_supervisor = "&".join([f'&supervisor={supervisor}' for supervisor in selected_supervisor])
    if selected_campus:
        filter_campus = '&'.join([f'&campus={campus}' for campus in selected_campus])
    if selected_course:
        filter_course = '&'.join([f'&course={course}' for course in selected_course])
    if selected_category:
        filter_category = '&'.join([f'&category={category}' for category in selected_category])

    page_obj, total_pages, start_num, end_num, total_pages, items_per_page, total_theses = paginator(request, theses)

    context = {
        'no_thesis': no_thesis,
        # for the paginator feature
        'page_obj': page_obj, 'total_pages': total_pages, 'start_num': start_num, 'end_num': end_num, 'total_theses': total_theses, 'items_per_page': items_per_page,
        # for the filter feature
        'supervisor_list': supervisor_count,
        'campus_list': campus_count,
        'course_list': course_count,
        'category_list': category_count,
        'selected_supervisor': selected_supervisor,
        'selected_campus': selected_campus,
        'selected_course': selected_course,
        'selected_category': selected_category,
        # for the mix of filter and paginator feature
        'filter_supervisor': filter_supervisor,
        'filter_campus': filter_campus,
        'filter_course': filter_course,
        'filter_category': filter_category,
        # new shortened thesis description
        'new_description': new_description,
    }

    return render(request, 'main/thesis_list.html', context)


@login_required
@account_type_required('admin', 'unit coordinator')
# functions for creating new data
def create_data(request):
    if request.method == 'POST':
        form = ThesisForm(request.POST)
        if form.is_valid():
            form_data = form.cleaned_data
            form.save()
            thesis = Thesis.objects.get(topic_number=form_data['topic_number'])
            context = {
                'type': 'created',
                'thesis': thesis,
                'page_title': 'Successfully Added ' + form_data['title']
            }
            return render(request, 'main/success.html', context)
    else:
        form = ThesisForm()

    context = {
        'form': form,
    }
    return render(request, 'main/create.html', context)


@login_required
@account_type_required('admin', 'unit coordinator')
# Delete data
def modify_or_delete(request, topic_number=None):
    if topic_number is None:
        if request.path == '/thesis/modify/':
            modify_or_delete = 'Modify'
        elif request.path == '/thesis/delete/':
            modify_or_delete = 'Delete'

        thesis = Thesis.objects.all()

        new_description = truncate_description(thesis)

        page_obj, total_pages, start_num, end_num, total_pages, items_per_page, total_theses = paginator(request, thesis)

        context = {
            'modify_or_delete': modify_or_delete,
            'thesis': thesis,
            'modify_or_delete_menu': True,
            'new_description': new_description,
            # for the paginator feature
            'page_obj': page_obj, 'total_pages': total_pages, 'start_num': start_num, 'end_num': end_num, 'total_theses': total_theses, 'items_per_page': items_per_page,
        }

        return render(request, "main/modify_or_delete.html", context)
    else:
        if request.path[:15] == '/thesis/modify/':
            modify_or_delete = 'Modify'
        elif request.path[:15] == '/thesis/delete/':
            modify_or_delete = 'Delete'

        try:
            # Fetch the thesis object to delete based on topic_number
            thesis = Thesis.objects.get(topic_number=topic_number)
            old_thesis_data = copy.copy(thesis)
            old_thesis_campus = copy.copy(thesis.campus.all())
            old_thesis_course = copy.copy(thesis.course.all())
            old_campus_list = [campus for campus in old_thesis_campus]
            old_course_list = [course for course in old_thesis_course]

        except Thesis.DoesNotExist:
            return render(request, 'main/success.html', {'fail': True})

        if request.method == 'POST':
            if modify_or_delete == 'Modify':
                form = ThesisForm(request.POST, instance=thesis)
                if form.is_valid() and form.has_changed():
                    form.save()

                    changed_data = changed_data_check(thesis, old_thesis_data, old_campus_list, old_course_list)

                    context = {
                        'type': 'modified',
                        'page_title': 'Successfully Edited ' + form.cleaned_data['title'],
                        # updated thesis data
                        'thesis': thesis,
                        # old thesis data
                        'old_thesis_data': old_thesis_data,
                        'old_campus_list': old_campus_list,
                        'old_course_list': old_course_list,
                        # entries that changed data
                        'changed_data': changed_data,
                    }
                    return render(request, 'main/success.html', context)

                elif not form.has_changed():
                    form = ThesisForm(instance=thesis)

                    context = {
                        'thesis': thesis,
                        'form': form,
                        'modify_or_delete_menu': False,
                        'modify_or_delete': modify_or_delete,
                        'error': True
                    }

                    return render(request, "main/modify_or_delete.html", context)

            elif modify_or_delete == 'Delete':
                try:
                    thesis.delete()
                    try:
                        ThesisRequestDelete.objects.get(topic_number=topic_number).delete()
                        reqeust_delete = True
                    except ThesisRequestDelete.DoesNotExist:
                        reqeust_delete = False
                    try:
                        ThesisRequestModify.objects.get(topic_number=topic_number).delete()
                        reqeust_modify = True
                    except ThesisRequestModify.DoesNotExist:
                        reqeust_modify = False
                    context = {
                        'thesis': thesis,
                        'old_thesis_data': old_thesis_data,
                        'old_campus_list': old_campus_list,
                        'old_course_list': old_course_list,
                        'type': 'deleted',
                    }
                    return render(request, 'main/success.html', context)
                except ProtectedError:
                    groups_enrolled = GroupApplicationAccepted.objects.filter(thesis=thesis)

                    context = {
                        'group_error': True,
                        'fail': True,
                        'thesis': thesis,
                        'groups_enrolled': groups_enrolled,
                    }
                    return render(request, 'main/success.html', context)

        else:
            if modify_or_delete == 'Modify':
                form = ThesisForm(instance=thesis)
            elif modify_or_delete == 'Delete':
                form = ThesisForm(instance=thesis)
                for field in form.fields.values():
                    field.widget.attrs['readonly'] = True
                    field.widget.attrs['disabled'] = True

        context = {
            'thesis': thesis,
            'form': form,
            'modify_or_delete_menu': False,
            'modify_or_delete': modify_or_delete,
        }

        return render(request, "main/modify_or_delete.html", context)


@login_required
@account_type_required('admin', 'unit coordinator')
def review_request(request, request_type=None, topic_number=None):
    if topic_number is None:
        thesis_list = list(ThesisRequestAdd.objects.all()) + list(ThesisRequestModify.objects.all()) + list(ThesisRequestDelete.objects.all())
        thesis = sorted(thesis_list, key=lambda x: x.request_date, )

        if not thesis_list:
            context = {
                'no_requests': True
            }
            return render(request, 'main/review_request.html', context)

        new_description = truncate_description(thesis)

        page_obj, total_pages, start_num, end_num, total_pages, items_per_page, total_theses = paginator(request, thesis)

        context = {
            'review_menu': True,
            'thesis': thesis,
            'new_description': new_description,
            # for the paginator feature
            'page_obj': page_obj, 'total_pages': total_pages, 'start_num': start_num, 'end_num': end_num, 'total_theses': total_theses, 'items_per_page': items_per_page,
        }
        return render(request, 'main/review_request.html', context)
    else:
        try:
            modify = False
            if request_type == 'create':
                thesis_to_review = ThesisRequestAdd.objects.get(topic_number=topic_number)
            elif request_type == 'modify':
                thesis_to_review = ThesisRequestModify.objects.get(topic_number=topic_number)
                modify = True
            elif request_type == 'delete':
                thesis_to_review = ThesisRequestDelete.objects.get(topic_number=topic_number)

            selected_action = request.POST.get('action')

            thesis_to_review_data = {
                'topic_number': thesis_to_review.topic_number,
                'title': thesis_to_review.title,
                'description': thesis_to_review.description,
                'category': thesis_to_review.category,
                'supervisor': thesis_to_review.supervisor,
                'group_taker_limit': thesis_to_review.group_taker_limit,
            }

            thesis_to_review_data_copy = copy.copy(thesis_to_review_data)
            thesis_to_review_data_campus = copy.copy(thesis_to_review.campus.all())
            thesis_to_review_data_course = copy.copy(thesis_to_review.course.all())

            old_thesis_data = None
            changed_data = None
            delete = None
            old_campus_list = None
            old_course_list = None

            try:
                old_thesis = Thesis.objects.get(topic_number=topic_number)
                old_thesis_data = copy.copy(old_thesis)
                old_thesis_campus = copy.copy(old_thesis.campus.all())
                old_thesis_course = copy.copy(old_thesis.course.all())
                old_campus_list = [campus for campus in old_thesis_campus]
                old_course_list = [course for course in old_thesis_course]
                old_thesis_exists = True

                changed_data = changed_data_check(thesis_to_review, old_thesis_data, old_campus_list, old_course_list)

            except Thesis.DoesNotExist:
                old_thesis_exists = False

            if selected_action == 'accept':
                if request_type == 'create':
                    thesis_to_create = Thesis.objects.create(**thesis_to_review_data)
                    thesis_to_create.campus.add(*Campus.objects.filter(campus__in=thesis_to_review_data_campus)),
                    thesis_to_create.course.add(*Course.objects.filter(course__in=thesis_to_review_data_course)),

                    thesis_to_review.delete()
                    type = 'accepted'
                    thesis_to_display = thesis_to_create

                elif request_type == 'modify':
                    old_thesis.delete()
                    thesis_to_modify = Thesis.objects.create(**thesis_to_review_data)
                    thesis_to_modify.campus.add(*Campus.objects.filter(campus__in=thesis_to_review_data_campus)),
                    thesis_to_modify.course.add(*Course.objects.filter(course__in=thesis_to_review_data_course)),

                    thesis_to_review.delete()

                    thesis_to_display = thesis_to_modify
                    type = 'modified'
                    modify = True

                elif request_type == 'delete':
                    old_thesis.delete()
                    thesis_to_review.delete()

                    thesis_to_display = old_thesis_data
                    type = 'deleted'
                    delete = True

                context = {
                    'thesis': thesis_to_display,
                    'requested_by': thesis_to_review.requested_by,
                    'request_date': thesis_to_review.request_date,
                    'request_type': thesis_to_review.request_type,
                    'type': type,
                    'delete': delete,
                    'modify': modify,
                    'old_thesis_data': old_thesis_data,
                    'old_campus_list': old_campus_list,
                    'old_course_list': old_course_list,
                    'changed_data': changed_data,
                }
                return render(request, 'main/success.html', context)

            elif selected_action == 'reject':
                thesis_to_review.delete()

                context = {
                    'rejected_thesis_request': True,
                    'type': 'rejected',
                    'old_thesis_data': thesis_to_review_data_copy,
                    'old_course_list': thesis_to_review_data_course,
                    'old_campus_list': thesis_to_review_data_campus,
                }

                return render(request, 'main/success.html', context)

        except Exception as e:
            context = {
                'error': True,
                'back_to_settings': True,
                'error_message': e
            }
            return render(request, 'main/account_error.html', context)

        context = {
            'request': True,
            'review_menu': False,
            'thesis': thesis_to_review,
            'modify_review': modify,
            'old_thesis_exists': old_thesis_exists,
            'old_thesis_data': old_thesis_data,
            'changed_data': changed_data,
        }
        return render(request, 'main/review_request.html', context)


@login_required
@account_type_required('admin', 'supervisor')
def request_crud(request, crud_action, status=None, topic_number=None):
    if crud_action == 'create':
        if request.method == 'POST':
            form = ThesisRequestFormAdd(request.POST)
            if form.is_valid():
                thesis_request = form.save(commit=False)
                thesis_request.requested_by = CustomUser.objects.get(username=request.user.username)
                thesis_request.request_type = crud_action
                thesis_request.supervisor = Supervisor.objects.get(supervisor=request.user)
                thesis_request.save()

                form.save_m2m()
                requested_thesis = ThesisRequestAdd.objects.get(topic_number=form.cleaned_data['topic_number'])

                context = {
                    'request': True,
                    'request_type': 'create',
                    'type': 'create',
                    'thesis': requested_thesis,
                    'requested_by': requested_thesis.requested_by,
                    'request_date': requested_thesis.request_date,
                }

                return render(request, 'main/success.html', context)

        else:
            form = ThesisRequestFormAdd()

        context = {
            'request': True,
            'request_type': 'create',
            'form': form
        }
        return render(request, 'main/request_crud.html', context)

    elif crud_action == 'modify' or crud_action == 'delete':
        if topic_number is None:
            if status is None:
                supervisor = Supervisor.objects.get(supervisor=request.user)
                thesis = Thesis.objects.filter(supervisor=supervisor)

                new_description = truncate_description(thesis)

                page_obj, total_pages, start_num, end_num, total_pages, items_per_page, total_theses = paginator(request, thesis)

                context = {
                    'request_type': crud_action,
                    'menu': True,
                    'thesis': thesis,
                    'new_description': new_description,
                    # for the paginator feature
                    'page_obj': page_obj, 'total_pages': total_pages, 'start_num': start_num, 'end_num': end_num, 'total_theses': total_theses, 'items_per_page': items_per_page,
                }

                return render(request, 'main/request_crud.html', context)

            else:
                pass
                '''
                if request.path[:31] == '/thesis/request/modify/pending/':
                    modify_or_delete = 'modify'
                elif request.path[:31] == '/thesis/request/delete/pending/':
                    modify_or_delete = 'delete'
                
                thesis_list = list(ThesisRequestAdd.objects.all()) + list(ThesisRequestModify.objects.all())
                thesis = sorted(thesis_list, key=lambda x: x.topic_number)


                context = {
                    
                }
                
                return render(request, 'main/request_crud.html', context)
                '''

        else:
            if request.path[:23] == '/thesis/request/modify/':
                modify_or_delete = 'modify'
            elif request.path[:23] == '/thesis/request/delete/':
                modify_or_delete = 'delete'

            exists_in_database = False
            thesis_exists = Thesis.objects.filter(topic_number=topic_number).exists()
            if thesis_exists:
                exists_in_database = True

            thesis = Thesis.objects.get(topic_number=topic_number)
            old_thesis_data = copy.copy(thesis)
            old_thesis_campus = copy.copy(old_thesis_data.campus.all())
            old_thesis_course = copy.copy(old_thesis_data.course.all())
            old_campus_list = [campus for campus in old_thesis_campus]
            old_course_list = [course for course in old_thesis_course]

            try:
                request_modify_exists = ThesisRequestModify.objects.get(topic_number=topic_number)
                request_exists_modify = True
            except ThesisRequestModify.DoesNotExist:
                request_exists_modify = False

            try:
                request_delete_exists = ThesisRequestDelete.objects.get(topic_number=topic_number)
                request_exists_delete = True
            except ThesisRequestDelete.DoesNotExist:
                request_exists_delete = False

            initial_form_data = {
                'topic_number': thesis.topic_number,
                'title': thesis.title,
                'description': thesis.description,
                'category': thesis.category,
                'supervisor': thesis.supervisor,
                'course': thesis.course.all(),
                'campus': thesis.campus.all(),
                'group_taker_limit': thesis.group_taker_limit,
            }

            if request.method == 'POST':
                if modify_or_delete == 'modify':
                    if request_exists_modify:
                        request_modify_exists.delete()

                    if request_exists_delete:
                        request_delete_exists.delete()

                    form = ThesisRequestFormModify(request.POST, initial=initial_form_data)
                    if form.is_valid() and form.has_changed():
                        thesis_request = form.save(commit=False)
                        thesis_request.requested_by = CustomUser.objects.get(username=request.user.username)
                        if exists_in_database:
                            thesis_request.request_type = crud_action
                        else:
                            thesis_request.request_type = 'add'

                        thesis_request.save()
                        form.save_m2m()

                        requested_thesis = ThesisRequestModify.objects.get(topic_number=form.cleaned_data['topic_number'])

                        changed_data = changed_data_check(requested_thesis, old_thesis_data, old_campus_list, old_course_list)

                        context = {
                            'request': True,
                            'request_type': 'modify',
                            'type': 'modify',
                            'thesis': requested_thesis,
                            'requested_by': requested_thesis.requested_by,
                            'request_date': requested_thesis.request_date,
                            'old_thesis_data': old_thesis_data,
                            'old_campus_list': old_campus_list,
                            'old_course_list': old_course_list,
                            'changed_data': changed_data,
                        }

                        return render(request, 'main/success.html', context)
                    elif form.has_changed() is not True:
                        form = ThesisRequestFormModify(initial=initial_form_data)

                        context = {
                            'request_exists_modify': request_exists_modify,
                            'request_exists_delete': request_exists_delete,
                            'form': form,
                            'request_type': 'modify',
                            'selected_thesis': thesis,
                            'no_change': True,
                        }

                        return render(request, 'main/request_crud.html', context)
                elif modify_or_delete == 'delete':
                    form = ThesisRequestFormDelete(initial_form_data)
                    for field in form.fields.values():
                        field.widget.attrs['readonly'] = True
                        field.widget.attrs['disabled'] = True
                    if form.is_valid():
                        thesis_request = form.save(commit=False)
                        thesis_request.requested_by = CustomUser.objects.get(username=request.user.username)
                        thesis_request.request_type = crud_action
                        thesis_request.save()

                        form.save_m2m()

                        requested_thesis = ThesisRequestDelete.objects.get(topic_number=form.cleaned_data['topic_number'])

                        context = {
                            'request': True,
                            'request_type': 'delete',
                            'type': 'delete',
                            'thesis': requested_thesis,
                            'requested_by': requested_thesis.requested_by,
                            'request_date': requested_thesis.request_date,
                        }

                        return render(request, 'main/success.html', context)

            else:
                if modify_or_delete == 'modify':
                    form = ThesisRequestFormModify(initial=initial_form_data)
                elif modify_or_delete == 'delete':
                    form = ThesisRequestFormDelete(instance=thesis)
                    for field in form.fields.values():
                        field.widget.attrs['readonly'] = True
                        field.widget.attrs['disabled'] = True

            context = {
                'request_exists_modify': request_exists_modify,
                'request_exists_delete': request_exists_delete,
                'form': form,
                'request_type': modify_or_delete,
                'menu': False,
                'selected_thesis': thesis,
            }
            return render(request, 'main/request_crud.html', context)


@login_required
@account_type_required('admin', 'supervisor', 'student')
def group_application(request, action, topic_number=None):
    if action == 'review':
        logged_in_supervisor = Supervisor.objects.get(supervisor=request.user)
        group_application_list = GroupApplication.objects.filter(thesis__supervisor=logged_in_supervisor, status='pending')

        selected_action = request.POST.get('action')
        selected_thesis = request.POST.get('thesis')
        selected_thesis_group = request.POST.get('student')

        if selected_action == 'accept':
            group_application_data = GroupApplication.objects.get(thesis__topic_number=selected_thesis, group__username=selected_thesis_group)
            group_application_data.status = 'accepted'
            group_application_data.save()
            cancelled_application = GroupApplication.objects.filter(group__username=selected_thesis_group, status='pending')
            for application in cancelled_application:
                application.status = 'cancelled'
                application.save()
            GroupApplicationAccepted.objects.create(group=group_application_data.group, status='accepted', thesis=group_application_data.thesis)

            accepted_application_count = GroupApplicationAccepted.objects.filter(thesis__topic_number=selected_thesis, status='accepted').count()
            thesis = Thesis.objects.get(topic_number=selected_thesis)
            group_limit = thesis.group_taker_limit
            if accepted_application_count == group_limit:
                remaining_applications = GroupApplication.objects.filter(thesis__topic_number=selected_thesis, status='pending')
                for application in remaining_applications:
                    application.status = 'cancelled'
                    application.save()

        elif selected_action == 'reject':
            group_application_data = GroupApplication.objects.get(thesis__topic_number=selected_thesis, group__username=selected_thesis_group)
            group_application_data.status = 'rejected'
            group_application_data.save()

        context = {
            'group_application_list': group_application_list,
        }

    elif action == 'view':
        logged_in_student = CustomUser.objects.get(username=request.user)
        try:
            accepted_application = [GroupApplication.objects.get(status='accepted', group__username=logged_in_student)]
            accepted_application_exists = True
        except GroupApplication.DoesNotExist:
            accepted_application_exists = False

        if accepted_application_exists:
            group_application_list = accepted_application
            applied_thesis_list = Thesis.objects.filter(topic_number__in=[group_application.thesis.topic_number for group_application in group_application_list])
            new_description = truncate_description(applied_thesis_list)
        else:
            group_application_list = GroupApplication.objects.filter(group__username=logged_in_student)

            applied_thesis_list = Thesis.objects.filter(topic_number__in=[group_application.thesis.topic_number for group_application in group_application_list])
            new_description = truncate_description(applied_thesis_list)

        try:
            if request.method == 'POST':
                cancel = request.POST.get('cancel')
                group_application_information = request.POST.get('thesis')
                if cancel == 'cancel':
                    GroupApplication.objects.get(group=logged_in_student, thesis__topic_number=group_application_information).delete()

                    return redirect('group_application', action='view')
        except GroupApplication.DoesNotExist:
            application_exists = False

        page_obj, total_pages, start_num, end_num, total_pages, items_per_page, total_theses = paginator(request, group_application_list)

        context = {
            'group_application_list': group_application_list,
            'new_description': new_description,
            'accepted_application_exists': accepted_application_exists,
            # for the paginator feature
            'page_obj': page_obj, 'total_pages': total_pages, 'start_num': start_num, 'end_num': end_num, 'total_theses': total_theses, 'items_per_page': items_per_page,
        }

    return render(request, 'main/group_application.html', context)


@login_required
@account_type_required('admin', 'unit coordinator')
# CRUD for entity (supervisor, campus, course, category)
def crud_entity(request, crud_action_entity, entity, name=None):
    entity_model_form_list = {
        'campus': (Campus, CampusForm),
        'category': (Category, CategoryForm),
        'course': (Course, CourseForm),
        'supervisor': (Supervisor, SupervisorForm)
    }

    model, form_entity = entity_model_form_list[entity]

    if crud_action_entity == 'add':
        if request.method == 'POST':
            form = form_entity(request.POST)
            if form.is_valid():
                cleaned_data = form.cleaned_data[entity]
                form.save()
                if entity == 'campus':
                    created_entity_object = model.objects.get(campus=cleaned_data)
                elif entity == 'category':
                    created_entity_object = model.objects.get(category=cleaned_data)
                elif entity == 'course':
                    created_entity_object = model.objects.get(course=cleaned_data)
                elif entity == 'supervisor':
                    created_entity_object = model.objects.get(supervisor=cleaned_data)

                context = {
                    'crud_action_entity': crud_action_entity,
                    'object_created': created_entity_object,
                    'crud_entity': True,
                    'entity': entity,
                    'page_title': f'{crud_action_entity} {entity}'
                }

                return render(request, 'main/success.html', context)
        else:
            form = form_entity

        context = {
            'form': form,
            'crud_action_entity': crud_action_entity,
            'entity': entity,
        }

        return render(request, 'main/CRUD_entity.html', context)

    elif crud_action_entity == 'modify' or crud_action_entity == 'delete':
        if not name:
            entity_model = model.objects.all()

            context = {
                'crud_action_entity': crud_action_entity,
                'entity': entity,
                'entity_model': entity_model,
                'menu': True,
            }
            return render(request, 'main/CRUD_entity.html', context)

        else:
            try:
                if entity == 'campus':
                    entity_object = model.objects.get(campus=name)
                elif entity == 'category':
                    entity_object = model.objects.get(category=name)
                elif entity == 'course':
                    entity_object = model.objects.get(course=name)
                elif entity == 'supervisor':
                    entity_object = model.objects.get(supervisor=name)
            except model.DoesNotExist:
                context = {
                    'entity_error': True,
                    'fail': True,
                    'entity': entity
                }
                return render(request, 'main/success.html', context)

            if crud_action_entity == 'modify':
                if request.method == 'POST':

                    form = form_entity(request.POST)
                    if form.is_valid() and form.has_changed():
                        old_object = copy.copy(name)
                        form.save()
                        cleaned_data = form.cleaned_data

                        if entity == 'campus':
                            modified_entity_object = model.objects.get(campus=cleaned_data['campus'])
                            model.objects.get(campus=name).delete()
                        elif entity == 'category':
                            modified_entity_object = model.objects.get(category=cleaned_data['category'])
                            model.objects.get(category=name).delete()
                        elif entity == 'course':
                            modified_entity_object = model.objects.get(course=cleaned_data['course'])
                            model.objects.get(course=name).delete()
                        elif entity == 'supervisor':
                            modified_entity_object = model.objects.get(supervisor=cleaned_data['supervisor'])
                            model.objects.get(supervisor=name).delete()

                        context = {
                            'old_object': old_object,
                            'crud_action_entity': crud_action_entity,
                            'modified_entity_object': modified_entity_object,
                            'crud_entity': True,
                            'entity': entity,
                            'page_title': f'{crud_action_entity} {entity}'
                        }
                        return render(request, 'main/success.html', context)
                    elif not form.has_changed():
                        form = form_entity(instance=entity_object)

                        context = {
                            'no_change': True,
                            'form': form,
                            'crud_action_entity': crud_action_entity,
                            'entity': entity,
                            'page_title': f'{crud_action_entity} {entity}'
                        }

                        return render(request, 'main/CRUD_entity.html', context)

                else:
                    form = form_entity(instance=entity_object)

                context = {
                    'crud_action_entity': crud_action_entity,
                    'entity': entity,
                    'form': form,
                }
                return render(request, 'main/CRUD_entity.html', context)
            elif crud_action_entity == 'delete':
                if request.method == 'POST':
                    old_object = copy.copy(entity_object)
                    try:
                        entity_object.delete()
                        context = {
                            'crud_action_entity': crud_action_entity,
                            'entity': entity,
                            'old_object': old_object,
                            'crud_entity': True,
                            'page_title': f'{crud_action_entity} {entity}'
                        }
                        return render(request, 'main/success.html', context)
                    except ProtectedError:
                        context = {
                            'protected_error': True,
                            'crud_action_entity': crud_action_entity,
                            'entity': entity,
                            'old_object': old_object,
                            'crud_entity': True,
                            'fail': True,
                            'page_title': f'{crud_action_entity} {entity}',
                            'entity_error': True
                        }
                        return render(request, 'main/success.html', context)

                form = form_entity(instance=entity_object)
                for field in form.fields.values():
                    field.widget.attrs['readonly'] = True
                    field.widget.attrs['disabled'] = True
                context = {
                    'crud_action_entity': crud_action_entity,
                    'entity': entity,
                    'form': form,
                }
                return render(request, 'main/CRUD_entity.html', context)


@login_required
@account_type_required('admin', 'unit coordinator', 'supervisor')
def admin_settings(request, account_type):

    return render(request, 'main/admin_settings.html')


@login_required
@account_type_required('admin', 'unit coordinator', 'supervisor')
def groups_thesis(request, topic_number):
    thesis = Thesis.objects.get(topic_number=topic_number)
    groups_in_thesis = GroupApplicationAccepted.objects.filter(thesis__topic_number=topic_number)
    groups_in_thesis_exists = False
    if groups_in_thesis:
        groups_in_thesis_exists = True

    current_supervisor = None
    try:
        current_supervisor = Supervisor.objects.get(supervisor=request.user)
        user_is_admin = False
    except Supervisor.DoesNotExist:
        user_is_admin = True

    responsible_supervisor = False
    if thesis.supervisor == current_supervisor or user_is_admin:
        responsible_supervisor = True

    if request.method == 'POST':
        group = CustomUser.objects.get(username=request.POST.get('group'))
        removed_group = GroupApplication.objects.get(group=group, thesis__topic_number=topic_number)

        removed_group.status = 'Rejected'
        removed_group.save()

        cancelled_application = GroupApplication.objects.filter(group__username=group, status='cancelled')
        for application in cancelled_application:
            application.status = 'pending'
            application.save()

        GroupApplicationAccepted.objects.get(group=removed_group.group, thesis=removed_group.thesis).delete()

        return redirect('groups_thesis', topic_number=topic_number)

    context = {
        'thesis': thesis,
        'groups_in_thesis': groups_in_thesis,
        'groups_in_thesis_exists': groups_in_thesis_exists,
        'responsible_supervisor': responsible_supervisor,
    }
    return render(request, 'main/groups_in_a_thesis.html', context)


'''       
FUNCTION FOR INSERTING SAMPLE DATA TO MODELS.PY 
-----------------------------------------------

def add_previous_data(request):
    campuses = ['Casuarina', 'Sydney', 'External']
    area = {
        'chemical': 'Chemical Engineering',
        'civil' : 'Civil and Structural Engineering',
        'electrical' :'Electrical and Electronics Engineering',
        'mechanical' : 'Mechanical Engineering',
        'computer' : 'Computer Science',
        'cyber' : 'Cyber Security',
        'data' : 'Data Science',
        'information' : 'Information Systems and Data Science',
        'software' : 'Software Engineering',
        } 
    categories = {
        'artificial' : 'Artificial Intelligence, Machine Learning and Data Science',
        'biomedical' : 'Biomedical Engineering and Health Informatics',
        'cyber' : 'Cyber Security',
    }
    supervisors = ['Bharanidharan Shanmugam', 'Yakub Sebastian', 'Sami Azam', 'Asif Karim']

    for campus in campuses:
        new_campus = Campus(campus = campus)
        new_campus.save()

    for course in area:
        new_course = Course(course = area[course])
        new_course.save()

    for category in categories:
        new_category = Category(category = categories[category])
        new_category.save()
    
    for supervisor in supervisors:
        new_supervisor = Supervisor(supervisor = supervisor)
        new_supervisor.save()
    
    thesis_1 = Thesis.objects.create(
        topic_number=1,       
        title= 'Machine learning approaches for Cyber Security',
        category= Category.objects.get(category = categories['artificial']),
        supervisor= Supervisor.objects.get(supervisor = supervisors[0]),
        description='As we use internet more, the data produced by us is enormous. But are these data being secure? The goal of applying machine learning or intelligence is to better risk modelling and prediction and for an informed decision support. Students will be working with either supervised or unsupervised machine learning approaches to solve the problem/s in the broader areas of Cyber Security.'
    )

    thesis_1.campus.add(*Campus.objects.filter(campus__in=campuses))
    thesis_1.course.add(*Course.objects.filter(course__in =[area['computer'], area['software']]))

    thesis_2 = Thesis.objects.create(
        topic_number= 9,
        title= 'Informetrics applications in multidisciplinary domain',
        category= Category.objects.get(category = categories['artificial']),
        supervisor= Supervisor.objects.get(supervisor = supervisors[1]),
        description='Informetrics studies are concerned with the quantitative aspects of information. The applications of advanced machine learning, information retrieval, network science and bibliometric techniques on various information artefact have contributed fresh insights into the evolutionary nature of research fields. This project aims at discovering informetric properties of multidisciplinary research literature using various machine learning, network analysis, data visualisation and data wrangling tools.'
    )
    thesis_2.campus.add(*Campus.objects.filter(campus__in=campuses))
    thesis_2.course.add(*Course.objects.filter(course__in = [area['computer'], area['cyber'], area['data'], area['information'], area['software']]))
     
    thesis_3 = Thesis.objects.create(
        topic_number=16,
        title='Development of a Virtual Reality System to Test Binaural Hearing',
        category=Category.objects.get(category = categories['biomedical']),
        supervisor= Supervisor.objects.get(supervisor = supervisors[2]),
        description='A virtual reality system could be used to objectively test the binaural hearing ability of humans (the ability to hear stereo and locate the direction and distance of sound). This project aims to design, implement and evaluate a VR system using standard off the shelf components (VR goggle and headphones) and standard programming techniques.'
    )
    thesis_3.campus.add(*Campus.objects.filter(campus__in=[campuses[0], campuses[2]]))
    thesis_3.course.add(*Course.objects.filter(course__in =[area['electrical'], area['computer'],  area['software']]))
    
    thesis_4 = Thesis.objects.create(
        topic_number=41,
        title='Current trends on cryptomining and its potential impact on cryptocurrencies',
        category= Category.objects.get(category = categories['cyber']),
        supervisor= Supervisor.objects.get(supervisor = supervisors[2]),
        description= "Cryptomining is the process of mining crypto currencies by running a sequence of algorithms. Traditionally, to mine new crypto coins, a person (or group of people) would buy expensive computers and spend a lot of time and money running them to perform the difficult calculations to generate crypto coins. Some website owners have started taking a different approach; they have put the software which runs those difficult calculations into their website's Javascript. This then causes the computers belonging to the visitors of their website to run those calculations for them, instead of running them themselves. In other words, when you visit a website with an embedded crypto-miner in it, your computer and electricity is used to try to generate crypto-coins for the owners of that website. Although there are various measures being applied to stop these illegitimate minings, the trend is still increasing. This research aims to find out potential gaps in current methodologies and develop a solution that can fulfil the gap. It also aims to find out: (1) What type crypto mining methodologies are being applied?, (2) Apart from crypto-mining, what other security risks may it introduce? For example: cryptojacking,  and (3) How current web standards are tackling this problem?"
    )
    thesis_4.campus.add(*Campus.objects.filter(campus__in=campuses))
    thesis_4.course.add(*Course.objects.filter(course__in =[area['computer'], area['cyber'], area['software']]))
    
    thesis_5 = Thesis.objects.create(
        topic_number=176,
        title='Artificial Intelligence in Health Informatics',
        category= Category.objects.get(category = categories['artificial']),
        supervisor= Supervisor.objects.get(supervisor = supervisors[3]),
        description='The project aims to use multiple publicly available health datasets to formulate a different dataset that may have features from the original set along with new ones developed through feature engineering. The dataset will then be used to build predictive model based on both general and deep learning based algorithm. The findings will be analysed and compared to similar research works.'
    )
    thesis_5.campus.add(*Campus.objects.filter(campus__in=campuses))
    thesis_5.course.add(*Course.objects.filter(course__in =[area['electrical'], area['computer'], area['data'], area['software']]))
    
    thesis_ = Thesis.objects.create(
        topic_number= 180,
        title='Unsupervised Model Development from Autism Screening Data',
        category= Category.objects.get(category = categories['artificial']),
        supervisor= Supervisor.objects.get(supervisor = supervisors[3]),
        description='The proposed system will present a two-cluster solution from a given dataset which will group toddlers based on multiple common medical traits. In depth literature survey of similar studies, both supervised and unsupervised will be carried out before the cluster-based model is implemented. The solution will be validated using both External and Internal validation measures and statistical significance tests.'
    )
    thesis_.campus.add(*Campus.objects.filter(campus__in=campuses))
    thesis_.course.add(*Course.objects.filter(course__in =[area['electrical'], area['computer'], area['data'], area['software']]))

    thesis_ = Thesis.objects.create(
        topic_number= 226,
        title= 'Applying Artificial Intelligence to solve real world problems',
        category= Category.objects.get(category = categories['artificial']),
        supervisor= Supervisor.objects.get(supervisor = supervisors[0]),
        description='Artificial Intelligence has been used in many applications to solve certain problems through out the academia and the industry – from electricity to writing text. AI has a multitude of applications and this project will pick up a problem and explore the applications of AI with minimal human intervention. Examples of applications include -building a bot, predicting the power usage, spam filtering and the list is endless.'
    )
    thesis_.campus.add(*Campus.objects.filter(campus__in=campuses))
    thesis_.course.add(*Course.objects.filter(course__in =[area['chemical'], area['civil'], area['computer'], area['cyber'], area['data'], area['electrical'], area['information'], area['mechanical'], area['software']]))
    return render(request, 'main/home.html')
'''
'''
FOR TROUBLESHOOTING PURPOSES
----------------------------
def data_retrieval_test(request):
    
    thesis_list = Thesis.objects.all()
    
    context = {
        'thesis_list': thesis_list,      
    }
    
    return render(request, 'main/data_retrieval_test.html', context)
'''
