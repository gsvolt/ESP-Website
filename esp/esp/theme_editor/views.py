from django.shortcuts import render_to_response
from django.template import RequestContext
from django.template import Context, Template
from esp.settings import PROJECT_ROOT
from django.http import HttpResponse, HttpResponseRedirect
from esp.users.models import admin_required
from os import path, remove
import re
import shutil
import glob

# can we avoid hardcoding this?
less_dir = path.join(PROJECT_ROOT, 'public/media/theme_editor/less/') #directory containing modified less files
variables_template_less = path.join(less_dir, 'variables_template.less')
variables_less = path.join(less_dir, 'variables.less')

sans_serif_fonts = {"Impact":"Impact, Charcoal, sans-serif",
                    "Palatino Linotype":"'Palatino Linotype', 'Book Antiqua', Palatino, serif",
                    "Tahoma":"Tahoma, Geneva, sans-serif",
                    "Century Gothic":"'Century Gothic', sans-serif",
                    "Lucida Sans Unicode":"'Lucida Sans Unicode', 'Lucida Grande', sans-serif",
                    "Arial Black":"'Arial Black', Gadget, sans-serif",
                    "Times New Roman":"'Times New Roman', Times, serif",
                    "Arial Narrow":"'Arial Narrow', sans-serif",
                    "Verdana":"Verdana, Geneva, sans-serif",
                    "Copperplate Gothic Light":"'Copperplate Gothic Light', Copperplate, sans-serif",
                    "Lucida Console":"'Lucida Console', Monaco, monospace",
                    "Gill Sans":"'Gill Sans', 'Gill Sans MT', sans-serif",
                    "Trebuchet MS":"'Trebuchet MS', Helvetica', sans-serif",
                    "Courier New":"'Courier New', Courier, monospace",
                    "Arial":"Arial, Helvetica, sans-serif",
                    "Georgia":"Georgia, serif"}

def get_theme_name(less_file):
    less_file = path.join(less_dir, less_file)
    f = open(less_file).read()
    d = {}
    theme_name = re.search(r"// Theme Name: (.+?)\n", f)
    if match:
        d.update({'theme_name':match.group(1)})
    return d

def parse_less(less_file):
    less_file = path.join(less_dir, less_file)
    try:
        f = open(less_file).read()
    #this regex is supposed to match @(property) = (value);
    #or @(property) = (function)(args) in match[0] and 
    #match[1] respectively
        matches = re.findall(r"@(\w+):\s*([^,;\(]*)[,;\(]", f)
        d = {}
        for match in matches:
            d[match[0]] = match[1]
        #in case color values like @white, @black are encountered, substitute
        #that with the hex value
            if match[1] and match[1][1:] in d and d[match[1][1:]][0] == '#':
                d[match[0]] = d[match[1][1:]]
    #if theme_name is set, retrieve that
        match = re.search(r"// Theme Name: (.+?)\n", f)
        if match:
            d.update({'theme_name':match.group(1)})
        return d
    except IOError:
        return {}

@admin_required    
def editor(request):
    context = parse_less(variables_less)
    # load a list of available themes
    available_themes_paths = glob.glob(path.join(less_dir,'theme_*.less'))
    available_themes = []
    for theme_path in available_themes_paths:
        available_themes.append(re.search(r'theme_editor/less/(theme_.+)\.less',theme_path).group(1))
    context.update({'available_themes':available_themes})
    context.update({'last_used_settings':'variables_backup'})
    context.update({'sans_fonts':sorted(sans_serif_fonts.iteritems())})
#    for debugging, see context by uncommenting the next line
#    return HttpResponse(str(context))

    return render_to_response('theme_editor/editor.html', context, context_instance=RequestContext(request))

def save(request, less_file):

    variables_settings = parse_less(less_file)

    # when the theme is saved for the first time, less_file doesn't exist, so parse_less will return an empty dict
    if not variables_settings or 'theme_name' not in variables_settings:
        variables_settings['theme_name'] = less_file[:-5]

        # if theme is saved without a name, just set it as default with the name 'None'
        if variables_settings['theme_name'] == '': 
            del variables_settings['theme_name']
    
    # if theme is only applied, just set theme as default and name as 'None'
    if 'apply' in request.POST:
        del variables_settings['theme_name']
    less_file = path.join(less_dir, less_file)
    f = open(variables_template_less)
    variables_template = Template(f.read())
    f.close()
    form_settings = dict(request.POST) # retrieve context from form input, change to POST eventually

    for k,v in form_settings.items():
        form_settings[k] = form_settings[k][0] # because QueryResponse objects store values as lists
        if not form_settings[k]: # if a form element returns no value, don't keep it in the context
            del form_settings[k];

    variables_settings.update(form_settings)
    w = variables_template.render(Context(variables_settings))
    f = open(less_file, 'w')
    f.write(w)
    f.close()

def apply_theme(less_file):
    # in case you are trying to restore the last used settings
    if less_file == 'variables_backup.less': 
        temp_file = path.join(less_dir, 'variables_backup_temp.less')
        try:
            shutil.copy(path.join(less_dir,less_file),temp_file)
            shutil.copy(variables_less, path.join(less_dir, less_file))
            shutil.copy(temp_file, variables_less)
            remove(temp_file)
        except shutil.Error:
            pass
        return

    less_file = path.join(less_dir, less_file)
    try:
        shutil.copy(path.join(less_dir,'variables_backup.less'),path.join(less_dir,'variables_backup_temp.less'))
        shutil.copy(variables_less, path.join(less_dir, 'variables_backup.less'))
        shutil.copy(less_file, variables_less)
    except shutil.Error:
        pass

@admin_required
def theme_submit(request):
    if 'save' in request.POST:
        save(request, request.POST['saveThemeName']+'.less')
        apply_theme(request.POST['saveThemeName']+'.less')
    elif 'load' in request.POST:
        apply_theme(request.POST['loadThemeName']+'.less')
    elif 'apply' in request.POST:
        shutil.copy(variables_less, path.join(less_dir,'variables_backup.less'))
        save(request, 'variables.less')
    elif 'reset' in request.POST:
        pass
    else: 
        return HttpResponseRedirect('/')
    return HttpResponseRedirect('/theme/')
