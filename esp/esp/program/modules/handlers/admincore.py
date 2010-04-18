
__author__    = "MIT ESP"
__date__      = "$DATE$"
__rev__       = "$REV$"
__license__   = "GPL v.2"
__copyright__ = """
This file is part of the ESP Web Site
Copyright (c) 2007 MIT ESP

The ESP Web Site is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software
Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

Contact Us:
ESP Web Group
MIT Educational Studies Program,
84 Massachusetts Ave W20-467, Cambridge, MA 02139
Phone: 617-253-4882
Email: web@esp.mit.edu
"""
from esp.program.modules.base import ProgramModuleObj, needs_teacher, needs_student, needs_admin, usercheck_usetl, CoreModule, main_call, aux_call
from esp.program.modules import module_ext
from esp.web.util        import render_to_response
from django.contrib.auth.decorators import login_required
from esp.datatree.models import *
from esp.users.models import User, UserBit
from django import forms
from django.forms.formsets import formset_factory

from esp.utils.forms import new_callback, grouped_as_table, add_fields_to_class
from esp.utils.widgets import DateTimeWidget
from esp.middleware import ESPError

from datetime import datetime



class UserBitForm(forms.ModelForm):
    def __init__(self, bit = None, *args, **kwargs):
        super(UserBitForm, self).__init__(*args, **kwargs)

        if bit != None:
            self.fields['startdate'] = forms.DateTimeField(initial=bit.startdate, widget=DateTimeWidget())
            self.fields['enddate'] = forms.DateTimeField(initial=bit.enddate, widget=DateTimeWidget(), required=False)
            self.fields['id'] = forms.IntegerField(initial=bit.id, widget=forms.HiddenInput())
            self.fields['qsc'] = forms.ModelChoiceField(queryset=DataTree.objects.all(), initial=bit.qsc.id, widget=forms.HiddenInput())
            self.fields['verb'] = forms.ModelChoiceField(queryset=DataTree.objects.all(), initial=bit.verb.id, widget=forms.HiddenInput())
        else:
            self.fields['startdate'] = forms.DateTimeField(widget=DateTimeWidget(), required=False)
            self.fields['enddate'] = forms.DateTimeField(widget=DateTimeWidget(), required=False)
            self.fields['id'] = forms.IntegerField(widget=forms.HiddenInput(), required=False)

        self.fields['user'] = forms.ModelChoiceField(queryset=User.objects.all(), widget=forms.HiddenInput(), required=False)
        
        self.fields['startdate'].line_group = 1
        self.fields['enddate'].line_group = 1
        self.fields['recursive'] = forms.BooleanField(label = 'Covers deadlines beneath it ("Recursive")', required=False) # I consider this a bug, though it makes sense in context of the form protocol: Un-checked BooleanFields are marked as having not been filled out
        self.fields['recursive'].line_group = 2
        
    as_table = grouped_as_table
    
    class Meta:
        model = UserBit

class EditUserbitForm(forms.Form):
    
    startdate = forms.DateTimeField(widget=DateTimeWidget())
    enddate = forms.DateTimeField(widget=DateTimeWidget(), required=False)
    recursive = forms.ChoiceField(choices=((True, 'Recursive'), (False, 'Individual')), widget=forms.RadioSelect, required=False) 
    id = forms.IntegerField(required=True, widget=forms.HiddenInput)


class AdminCore(ProgramModuleObj, CoreModule):

    @classmethod
    def module_properties(cls):
        return {
            "link_title": "Program Dashboard",
            "module_type": "manage",
            "seq": -9999
            }

    @aux_call
    @needs_admin
    def main(self, request, tl, one, two, module, extra, prog):
        context = {}
        modules = self.program.getModules(self.user, 'manage')
                    
        context['modules'] = modules
        context['one'] = one
        context['two'] = two

        return render_to_response(self.baseDir()+'directory.html', request, (prog, tl), context)

    @main_call
    @needs_admin
    def dashboard(self, request, tl, one, two, module, extra, prog):
        """ The administration panel showing statistics for the program, and a list
        of classes with the ability to edit each one.  """
        
        context = {}
        modules = self.program.getModules(self.user, 'manage')
        
        for module in modules:
            context = module.prepare(context)
 
        context['modules'] = modules
        context['one'] = one
        context['two'] = two

        return render_to_response(self.baseDir()+'mainpage.html', request, (prog, tl), context)

    @aux_call
    @needs_admin
    def deadline_management(self, request, tl, one, two, module, extra, prog):
        #   Define a formset for editing multiple user bits simultaneously.
        EditUserbitFormset = formset_factory(EditUserbitForm)
    
        #   Handle 'open' / 'close' actions
        if extra == 'open' and 'id' in request.GET:
            bit = UserBit.objects.get(id=request.GET['id'])
            bit.renew()
        elif extra == 'close' and 'id' in request.GET:
            bit = UserBit.objects.get(id=request.GET['id'])
            bit.expire()
            
        #   Check incoming form data
        if request.method == 'POST':
            edit_formset = EditUserbitFormset(request.POST.copy())
            if edit_formset.is_valid(): 
                for form in edit_formset.forms:
                    if 'id' in form.cleaned_data:
                        bit = UserBit.objects.get(id=form.cleaned_data['id'])
                        bit.startdate = form.cleaned_data['startdate']
                        bit.enddate = form.cleaned_data['enddate']
                        bit.recursive = (form.cleaned_data['recursive'] == u'True')
                        bit.save()
    
        #   Get a list of Datatree nodes corresponding to user bit verbs
        deadline_verb = GetNode("V/Deadline/Registration")
        nodes = deadline_verb.descendants().exclude(id=deadline_verb.id).order_by('uri')

        #   Build a list of user bits that reference the relevant verbs
        bits = []
        bit_map = {}
        for v in nodes:
            selected_bits = UserBit.objects.filter(qsc=self.program_anchor_cached(), verb=v, user__isnull=True).order_by('-id')
            if selected_bits.count() > 0:
                bits.append(selected_bits[0])
                bit_map[v.uri] = selected_bits[0]

        #   Render page with forms
        context = {}

        for bit in bits:
            if bit.enddate > datetime.now():
                bit.open_now = True
            else:
                bit.open_now = False
            bit.includes = bit.verb.descendants().exclude(id=bit.verb.id)
            for node in bit.includes:
                if node in nodes and node.uri in bit_map:
                    node.overridden = True
                    node.overridden_by = bit_map[node.uri]
            
        #   Supply initial data from user bits for forms
        formset = EditUserbitFormset(initial=[bit.__dict__ for bit in bits])
        for i in range(len(bits)):
            bits[i].form = formset.forms[i]
        
        context['manage_form'] = formset.management_form
        context['bits'] = bits
        
        return render_to_response(self.baseDir()+'deadlines.html', request, (prog, tl), context) 
        
    #   Alias for deadline management
    deadlines = deadline_management
        
    def isStep(self):
        return True
    
 

