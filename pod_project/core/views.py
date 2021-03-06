# -*- coding: utf-8 -*-
from __future__ import unicode_literals
"""
Copyright (C) 2014 Nicolas Can
Ce programme est un logiciel libre : vous pouvez
le redistribuer et/ou le modifier sous les termes
de la licence GNU Public Licence telle que publiée
par la Free Software Foundation, soit dans la
version 3 de la licence, ou (selon votre choix)
toute version ultérieure.
Ce programme est distribué avec l'espoir
qu'il sera utile, mais SANS AUCUNE
GARANTIE : sans même les garanties
implicites de VALEUR MARCHANDE ou
D'APPLICABILITÉ À UN BUT PRÉCIS. Voir
la licence GNU General Public License
pour plus de détails.
Vous devriez avoir reçu une copie de la licence
GNU General Public Licence
avec ce programme. Si ce n'est pas le cas,
voir http://www.gnu.org/licenses/
"""

from django.shortcuts import render
from core.forms import FileBrowseForm, ProfileForm, ContactUsModelForm
from django.shortcuts import render_to_response, get_object_or_404
from django.http import Http404, HttpResponseRedirect
from django.template import RequestContext

from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.decorators import login_required
from django.views.decorators.csrf import csrf_protect
from django.core.mail import EmailMultiAlternatives
from django.contrib import messages

from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import logout
from django.core.urlresolvers import reverse
from django.contrib.auth import authenticate, login
from django.template.loader import render_to_string
from django.utils.http import urlquote
from django.utils.html import strip_tags

from django.conf import settings
import sys

import logging
logger = logging.getLogger(__name__)

@login_required
def file_browse(request):
    # Add this to improve folder selection and view list
    if not request.session.get('filer_last_folder_id'):
        from filer.models import Folder
        folder = Folder.objects.get(
            owner=request.user, name=request.user.username)
        request.session['filer_last_folder_id'] = folder.id
    form = FileBrowseForm()  # A empty, unbound form
    fic = None
    get_CKEditorFuncNum = None
    if request.GET.get('CKEditorFuncNum'):
        get_CKEditorFuncNum = "%s" % request.GET['CKEditorFuncNum']
    if request.method == 'POST':
        form = FileBrowseForm(request.POST)
        if form.is_valid():
            fic = form.cleaned_data['document']
    return render_to_response("fileBrowse.html",
                              {'form': form, 'fic': fic,
                                  'get_CKEditorFuncNum': get_CKEditorFuncNum},
                              context_instance=RequestContext(request))


@csrf_protect
def core_login(request):
    # on determine la page ou renvoyer l'utilisateur
    next = request.GET['next'] if request.GET.get('next') else request.POST['next'] if request.POST.get(
        'next') else request.META['HTTP_REFERER'] if request.META.get('HTTP_REFERER') else "/"

    if settings.USE_CAS and not request.GET.get("gateway") and not request.POST:
        if request.GET.get("is_iframe"):
            return HttpResponseRedirect(reverse('cas_login') + '?gateway=True&next=%s&is_iframe=true' % urlquote(next))
        else:
            return HttpResponseRedirect(reverse('cas_login') + '?gateway=True&next=%s' % urlquote(next))

    if request.user.is_authenticated():
        return HttpResponseRedirect(next)  # Redirect to a success page.

    form = AuthenticationForm()
    # placeholder
    from django import forms
    form.fields['username'].widget = forms.TextInput(
        attrs={'placeholder': _('Login')})
    form.fields['password'].widget = forms.PasswordInput(
        attrs={'placeholder': _('Password')})

    if request.POST and request.POST['username'] and request.POST['password']:
        user = authenticate(
            username=request.POST['username'], password=request.POST['password'])
        if user is not None:
            if user.is_active:
                login(request, user)
                try:
                    user.userprofile.auth_type = "loc"
                    user.userprofile.save()
                except:
                    msg = u'\n*****Unexpected error link :%s - %s' % (
                        sys.exc_info()[0], sys.exc_info()[1])
                    logger.error(msg)
                # Redirect to a success page.
                return HttpResponseRedirect(next)
            else:
                # Return a 'disabled account' error message
                msg = u'%s' % _(
                    u'Your account is disabled, please contact the administrator of the platform.')
                messages.add_message(request, messages.ERROR, msg)
        else:
            # Return an 'invalid login' error message.
            msg = u'%s' % _(
                u'Unable to connect. Please check your credentials and try again, or contact the platform administrator.')
            messages.add_message(request, messages.ERROR, msg)

    return render_to_response("registration/login.html",
                              {'form': form, 'next': next,
                                  "USE_CAS": settings.USE_CAS},
                              context_instance=RequestContext(request))


def core_logout(request):
    logout(request)
    if settings.USE_CAS:
        return HttpResponseRedirect(reverse('cas_logout'))
    else:
        return HttpResponseRedirect("/")


@csrf_protect
@login_required
def user_profile(request):
    # Add this to improve folder selection
    if not request.session.get('filer_last_folder_id'):
        from filer.models import Folder
        folder = Folder.objects.get(
            owner=request.user, name=request.user.username)
        request.session['filer_last_folder_id'] = folder.id
    try:
        profile_form = ProfileForm(instance=request.user.userprofile)
    except:
        profile_form = ProfileForm()

    if request.POST:
        try:
            profile_form = ProfileForm(
                request.POST, instance=request.user.userprofile)
        except:
            profile_form = ProfileForm(request.POST)

        if profile_form.is_valid():
            profile = profile_form.save(commit=False)
            profile.user = request.user
            profile.save()
            messages.add_message(
                request, messages.INFO, _(u'Your profile is saved.'))
        else:
            messages.add_message(
                request, messages.ERROR, _(u'One or more errors have been found in the form.'))

    return render_to_response("userProfile.html",
                              {'form': profile_form, },
                              context_instance=RequestContext(request))


@csrf_protect
def contact_us(request):
    if request.POST:
        form = ContactUsModelForm(request, request.POST)
        # Validate the form: the captcha field will automatically
        # check the input
        if form.is_valid():
            contact = form.save()
            msg_html = _(u'\n<p>The user %(sender_name)s &lt;<a href=\"mailto:%(sender_email)s\">%(sender_email)s</a>&gt; send a message from <strong>%(site_title)s.</strong></p>\n'
                         '<p>Here is the message sent : <br/>\n\n'
                         '%(message)s</p>\n\n'
                         '<p>Referrer page : <a href=\"%(url)s\">%(url)s</a></p>\n\n'
                         ) % {
                'sender_name': contact.name, 'site_title': settings.TITLE_SITE,
                'sender_email': contact.email, 'message': contact.message.replace("\n","<br/>"), 
                'url': form.cleaned_data['url_referrer']
                }
            msg_txt = strip_tags(u'%s' %msg_html)

            email_msg = EmailMultiAlternatives(
                "[" + settings.TITLE_SITE + "]  %s" %contact.subject, msg_txt, contact.email, settings.REPORT_VIDEO_MAIL_TO)
            email_msg.attach_alternative(msg_html, "text/html")
            email_msg.send(fail_silently=False)

            msg_html = _(u'\n<p>You just send a message from <strong>%(site_title)s.</strong></p>\n'
                         '<p>Here is the message sent : <br/>\n\n'
                         '%(message)s</p>\n\n'
                         '<p>Regards</p>\n\n'
                         ) % {
                'site_title': settings.TITLE_SITE,
                'message': contact.message.replace("\n","<br/>")
                }
            msg_txt = strip_tags(u'%s' %msg_html)

            email_msg = EmailMultiAlternatives(
                "[" + settings.TITLE_SITE + "] %s %s" %(_('your message intitled'), contact.subject), msg_txt, settings.HELP_MAIL, [contact.email])
            email_msg.attach_alternative(msg_html, "text/html")
            email_msg.send(fail_silently=False)

            messages.add_message(
                request, messages.INFO, _(u'Your message has been sent.'))
            return HttpResponseRedirect(form.cleaned_data['url_referrer'])
    else:
        if request.user.is_authenticated():
            form = ContactUsModelForm(request, initial={"name":request.user.get_full_name(), "email":request.user.email, "url_referrer": request.META.get('HTTP_REFERER', request.build_absolute_uri("/"))})
        else:
            form = ContactUsModelForm(request, initial={"url_referrer": request.META.get('HTTP_REFERER', request.build_absolute_uri("/"))})

    form_html = render_to_string('contactus/contactus.html', {'form': form}, context_instance=RequestContext(request))

    flatpage = {'title':_("Contact us"), "content":form_html}
    return render_to_response('flatpages/default.html',
                              {'flatpage': flatpage, },
                              context_instance=RequestContext(request))

