from esp.program.models import Program
from esp.program.modules.base import ProgramModuleObj, needs_teacher, main_call, meets_deadline
from esp.web.util        import render_to_response
from esp.users.models   import ESPUser, Record
from esp.datatree.models import GetNode
from django import forms
from django.db.models.query import Q
from esp.middleware.threadlocalrequest import get_current_request

def teacheracknowledgementform_factory(prog):
    name = "TeacherAcknowledgementForm"
    bases = (forms.Form,)
    label = u"I have read the above, and commit to teaching my %s class on %s." % (prog.program_type, prog.date_range())
    d = dict(acknowledgement=forms.BooleanField(required=True, label=label))
    return type(name, bases, d)

class TeacherAcknowledgementModule(ProgramModuleObj):
    @classmethod
    def module_properties(cls):
        return {
            "admin_title": "Teacher Acknowledgement",
            "link_title": "Teacher Acknowledgement",
            "module_type": "teach",
            "required": False,
        }
    
    def isCompleted(self):
        return Record.objects.filter(user=get_current_request().user,
                                     program=self.program,
                                     event="teacheracknowledgement").exists()
    
    @main_call
    @needs_teacher
    @meets_deadline('/Acknowledgement')
    def acknowledgement(self, request, tl, one, two, module, extra, prog):
        context = {'prog': prog}
        if request.method == 'POST':
            context['form'] = teacheracknowledgementform_factory(prog)(request.POST)
            rec, created = Record.objects.get_or_create(user=request.user,
                                                        program=self.program,
                                                        event="teacheracknowledgement")
            if context['form'].is_valid():
                return self.goToCore(tl)
            else:
                rec.delete()
        elif self.isCompleted():
            context['form'] = teacheracknowledgementform_factory(prog)({'acknowledgement': True})
        else:
            context['form'] = teacheracknowledgementform_factory(prog)()
        return render_to_response(self.baseDir()+'acknowledgement.html', request, (prog, tl), context)
    
    def teachers(self, QObject = False):
        """ Returns a list of teachers who have submitted the acknowledgement. """
        from datetime import datetime
        qo = Q(record__program=self.program, record__event="teacheracknowledgement")
        if QObject is True:
            return {'acknowledgement': self.getQForUser(qo)}
        
        teacher_list = ESPUser.objects.filter(qo).distinct()
        
        return {'acknowledgement': teacher_list }

    def teacherDesc(self):
        return {'acknowledgement': """Teachers who have submitted the acknowledgement for the program."""}    
    
    class Meta:
        abstract = True
    


