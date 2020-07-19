try:
    import requests
    import datetime
    import locale
    import matplotlib.pyplot as plt
    import os
    import traceback
except ModuleNotFoundError as module_error:
    print(str(module_error) + ". You should install it.")


def extract_data(source_url):
    """Get json data from url and create a dictionary containing it."""
    request_result = requests.get(source_url)
    source_json = request_result.json()
    return source_json


def create_dictionaries_per_country(source_data):
    """Create dictionaries based on source data."""
    covid_cases = {}
    """
        - date
            - region
    """
    regions_info = {}
    """
        - region
            - continent
            - population
    """
    for record in source_data['records']:
        date = datetime.datetime.strptime(record['dateRep'], '%d/%m/%Y')
        date_key = date.strftime('%Y-%m-%d')
        region = record['countriesAndTerritories'].lower()
        continent = record['continentExp'].lower()
        cases = int(record['cases'])
        if record['popData2019'] is not None:
            population = int(record['popData2019'])
        if date_key not in covid_cases:
            covid_cases[date_key] = {}
        if region not in covid_cases[date_key]:
            covid_cases[date_key][region] = {}
            covid_cases[date_key][region] = cases
        if region not in regions_info:
            regions_info[region] = {}
            regions_info[region]['population'] = population
            regions_info[region]['continent'] = continent
    return covid_cases, regions_info


def repair_negative_cases(covid_cases):
    """Check for negative cases and bring them to previous days."""
    covid_cases_date_keys_desc = sorted(covid_cases.keys(), reverse=True)
    for date_key in covid_cases_date_keys_desc:
        for region in covid_cases[date_key]:
            if covid_cases[date_key][region] < 0:
                cases_for_move = covid_cases[date_key][region]
                covid_cases[date_key][region] = 0
                for backward_date_key in covid_cases_date_keys_desc:
                    if backward_date_key < date_key and region in covid_cases[backward_date_key]:
                        covid_cases[backward_date_key][region] += cases_for_move
                        break
    return covid_cases


def sum_cases_for_world_and_continents(covid_cases, regions_info):
    """Sum cases for world and continents."""
    for date_key in covid_cases:
        cases_continents = {}
        for region in covid_cases[date_key]:
            continent = regions_info[region]['continent']
            if continent not in cases_continents:
                cases_continents[continent] = 0
            cases_continents[continent] += covid_cases[date_key][region]
        covid_cases[date_key]['world'] = 0
        for continent in cases_continents:
            covid_cases[date_key][continent] = cases_continents[continent]
            covid_cases[date_key]['world'] += cases_continents[continent]
    return covid_cases


def sum_population_for_world_and_continents(regions_info):
    """Sum population for world and continents."""
    population_continents = {}
    for region in regions_info:
        continent = regions_info[region]['continent']
        if continent not in population_continents:
            population_continents[continent] = {}
            population_continents[continent]['population'] = 0
        population_continents[continent]['population'] += regions_info[region]['population']
    regions_info['world'] = {}
    regions_info['world']['population'] = 0
    for continent in population_continents:
        regions_info[continent] = {}
        regions_info[continent]['population'] = population_continents[continent]['population']
        regions_info['world']['population'] += population_continents[continent]['population']
    return regions_info


def transform_data(source_data):
    """Transform source data to covid_cases and regions_info."""
    covid_cases, regions_info = create_dictionaries_per_country(source_data)
    covid_cases = repair_negative_cases(covid_cases)
    covid_cases = sum_cases_for_world_and_continents(covid_cases, regions_info)
    regions_info = sum_population_for_world_and_continents(regions_info)
    return covid_cases, regions_info


def generate_time_range(as_of_date, weeks_range):
    """Generate a list containing dates from a weeks_range."""
    as_of_date = datetime.datetime.strptime(as_of_date, '%Y-%m-%d')
    as_of_date_week_day = as_of_date.weekday()
    time_range = [as_of_date - datetime.timedelta(days=x) for x in
                  range((as_of_date_week_day + (weeks_range - 1) * 7), -1 - (6 - as_of_date_week_day), -1)]
    return time_range


def create_week_cases_and_time_axis_series(region, covid_cases, time_range):
    """Create dictionaries with data series and axis for week cases chart. Week day is a key in covid_cases."""
    week_cases = {}
    time_axis = []
    for day in time_range:
        week_day = day.weekday()
        iso_week = str(day.isocalendar()[1]).zfill(2)
        date_key = day.strftime('%Y-%m-%d')
        if iso_week not in time_axis:
            time_axis.append(iso_week)
        cases = 0
        if date_key in covid_cases:
            if region in covid_cases[date_key]:
                cases = covid_cases[date_key][region]
        if week_day not in week_cases:
            week_cases[week_day] = []
        week_cases[week_day].append(cases)
    return week_cases, time_axis


def calculate_week_cases_running_sum(week_cases):
    """Calculate week cases running sums.  Week day is a key."""
    week_cases_running = {}
    for week_day in range(1, 6):
        week_cases_running[week_day] = []
        for day_number in range(len(week_cases[0])):
            if week_day == 1:
                day_cases_running = week_cases[week_day - 1][day_number] + week_cases[week_day][day_number]
            else:
                day_cases_running = week_cases_running[week_day - 1][day_number] + week_cases[week_day][day_number]
            week_cases_running[week_day].append(day_cases_running)
    return week_cases_running


def implement_common_chart_formatting(formatting):
    """Implement common formatting for charts."""
    ax = plt.gca()
    ax.yaxis.grid(color=formatting['grid_color'], linewidth=formatting['grid_line_width'])
    ax.get_yaxis().set_major_formatter(plt.FuncFormatter(lambda x, loc: formatting['y_axis_format'].format(int(x))))
    plt.xlabel(formatting['x_label'])
    plt.ylabel(formatting['y_label'])
    fig = plt.gcf()
    fig.set_size_inches(formatting['chart_width_inches'], formatting['chart_height_inches'])
    fig.tight_layout()
    fig.text(formatting['description_x'], formatting['description_y'], formatting['description_text'],
             fontsize=formatting['description_font_size'])


def create_week_cases_chart(region, covid_cases, time_range, common_formatting, chart_formatting):
    """Create week cases chart and save it as an image."""
    week_cases, time_axis = create_week_cases_and_time_axis_series(region, covid_cases, time_range)
    week_cases_running = calculate_week_cases_running_sum(week_cases)

    p0 = plt.bar(time_axis, week_cases[0])
    p1 = plt.bar(time_axis, week_cases[1], bottom=week_cases[0])
    p2 = plt.bar(time_axis, week_cases[2], bottom=week_cases_running[1])
    p3 = plt.bar(time_axis, week_cases[3], bottom=week_cases_running[2])
    p4 = plt.bar(time_axis, week_cases[4], bottom=week_cases_running[3])
    p5 = plt.bar(time_axis, week_cases[5], bottom=week_cases_running[4])
    p6 = plt.bar(time_axis, week_cases[6], bottom=week_cases_running[5])

    plt.legend((p0[0], p1[0], p2[0], p3[0], p4[0], p5[0], p6[0]),
               chart_formatting['legend'])
    title = chart_formatting['title'].replace('{region}', region.capitalize())
    plt.title(title)
    implement_common_chart_formatting(common_formatting)
    path = chart_formatting['path'].replace('{region}', region)
    plt.savefig(path)
    plt.close()


def create_week_cases_per_100k_chart(region, covid_cases, regions_info, time_range, common_formatting,
                                     chart_formatting):
    """Create week cases per 100k chart and save it as an image."""
    closed_weeks_cases = []
    lasting_week_cases = []
    time_axis = []

    covid_cases_keys_asc = sorted(covid_cases.keys())
    last_day = datetime.datetime.strptime(covid_cases_keys_asc[-1], '%Y-%m-%d')
    first_date = datetime.datetime.strptime(covid_cases_keys_asc[0], '%Y-%m-%d')
    previous_week_number = str(first_date.isocalendar()[1]).zfill(2)
    cases = 0
    for date_key in covid_cases_keys_asc:
        date = datetime.datetime.strptime(date_key, '%Y-%m-%d')
        week_number = str(date.isocalendar()[1]).zfill(2)
        if date in time_range and (week_number != previous_week_number or date == last_day):
            time_axis.append(week_number)
            week_day = date.weekday()
            population = regions_info[region]['population']
            cases_per_100k = round(cases / population * 100000, 2)
            if date == last_day and week_day != 6:
                closed_weeks_cases.append(0)
                lasting_week_cases.append(cases_per_100k)
            else:
                closed_weeks_cases.append(cases_per_100k)
                lasting_week_cases.append(0)
            previous_week_number = week_number
        if region in covid_cases[date_key]:
            cases += covid_cases[date_key][region]

    p0 = plt.bar(time_axis, closed_weeks_cases)
    p1 = plt.bar(time_axis, lasting_week_cases)

    plt.legend((p0[0], p1[0]), chart_formatting['legend'])
    title = chart_formatting['title'].replace('{region}', region.capitalize())
    plt.title(title)
    implement_common_chart_formatting(common_formatting)
    path = chart_formatting['path'].replace('{region}', region)
    plt.savefig(path)
    plt.close()


def create_report(settings, as_of_date):
    """Create report based on a template file."""
    f = open(settings['template_path'], "r")
    contents = f.read()
    f.close()
    contents = contents.replace('{as_of_date}', as_of_date)
    contents = contents.replace('src="', 'src="' + settings['src_catalog'])
    f = open(settings['title'], "w+")
    f.write(contents)
    f.close()


def main():
    DEBUG_MODE = False

    try:
        # settings
        SOURCE_URL = 'https://opendata.ecdc.europa.eu/covid19/casedistribution/json/'
        WEEKS_RANGE = 24
        # regions should be written lowercase
        CHART_REGIONS = ['poland', 'europe', 'world']
        COMMON_CHART_FORMATING = {
            'grid_color': '0.05'
            , 'grid_line_width': 0.25
            , 'y_axis_format': '{0:n}'
            , 'x_label': 'weeks'
            , 'y_label': 'cases'
            , 'chart_width_inches': 7.2
            , 'chart_height_inches': 4.8
            , 'description_x': 0.6
            , 'description_y': 0.01
            , 'description_text': 'source: European Centre for Disease Prevention and Control'
            , 'description_font_size': 6
        }
        WEEK_CASES_CHART_FORMATTING = {
            'title': '{region} - weekly new COVID-19 cases.'
            , 'path': 'src/{region}_new_cases.png'
            , 'legend': ('monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday')
        }
        WEEK_CASES_PER_100K_CHART_FORMATTING = {
            'title': '{region} - COVID-19 cases (incremental) per 100,000 inhabitants.'
            , 'path': 'src/{region}_cases_per_100k.png'
            , 'legend': ('closed weeks', 'lasting week')
        }
        REPORT_SETTINGS = {
            'template_path': 'src/template.html'
            , 'title': 'COVID-19_report.html'
            , 'src_catalog': 'src/'
        }

        # set locale for readable number formatting
        locale.setlocale(locale.LC_ALL, '')

        source_data = extract_data(SOURCE_URL)

        covid_cases, regions_info = transform_data(source_data)

        as_of_date = sorted(covid_cases.keys())[-1]

        time_range = generate_time_range(as_of_date, WEEKS_RANGE)

        for region in CHART_REGIONS:
            create_week_cases_chart(region, covid_cases, time_range, COMMON_CHART_FORMATING,
                                    WEEK_CASES_CHART_FORMATTING)
            create_week_cases_per_100k_chart(region, covid_cases, regions_info, time_range, COMMON_CHART_FORMATING,
                                             WEEK_CASES_PER_100K_CHART_FORMATTING)

        create_report(REPORT_SETTINGS, as_of_date)

        os.system('start ' + REPORT_SETTINGS['title'])

    except requests.exceptions.RequestException:
        if DEBUG_MODE:
            traceback.print_exc()
        else:
            print("I can't download data from " + SOURCE_URL +
                  "/n Check your internet connection and try again.")

    except ValueError:
        if DEBUG_MODE:
            traceback.print_exc()
        else:
            print("I can't read data from " + SOURCE_URL +
                  "/n The data structure was probably changed.")

    except FileNotFoundError:
        if DEBUG_MODE:
            traceback.print_exc()
        else:
            print("The program's file structure has been corrupted. Download the program again.")

    except:
        if DEBUG_MODE:
            traceback.print_exc()
        else:
            print("There was unexpected error. Try to run program again.")


if __name__ == "__main__":
    main()
