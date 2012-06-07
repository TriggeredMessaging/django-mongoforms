from operator import attrgetter

from django import forms
from django.utils.encoding import smart_unicode
from bson.errors import InvalidId
from bson.objectid import ObjectId

from widgets import ListWidget


class ReferenceField(forms.ChoiceField):
    """
    Reference field for mongo forms.
    Inspired by `django.forms.models.ModelChoiceField`.
    """
    def __init__(self, queryset, *aargs, **kwaargs):
        forms.Field.__init__(self, *aargs, **kwaargs)
        self.queryset = queryset

    def _get_queryset(self):
        return self._queryset

    def _set_queryset(self, queryset):
        self._queryset = queryset
        self.widget.choices = self.choices

    queryset = property(_get_queryset, _set_queryset)

    def _get_choices(self):
        if hasattr(self, '_choices'):
            return self._choices

        self._choices = [(obj.id, smart_unicode(obj)) for obj in self.queryset]
        return self._choices

    choices = property(_get_choices, forms.ChoiceField._set_choices)

    def clean(self, value):
        try:
            oid = ObjectId(value)
            oid = super(ReferenceField, self).clean(oid)
            if 'id' in self.queryset._query_obj.query:
                obj = self.queryset.get()
            else:
                obj = self.queryset.get(id=oid)
        except (TypeError, InvalidId, self.queryset._document.DoesNotExist):
            raise forms.ValidationError(
                self.error_messages['invalid_choice'] % {'value': value})
        return obj


class ListField(forms.MultiValueField):
    """
    List field for mongo forms.
    Uses MultiValueField from django.forms module.
    """
    field_name_separator = '__'

    def __init__(self, field, field_name_base, list_size=2, *args, **kwargs):
        forms.Field.__init__(self, *args, **kwargs)
        self.fields = []
        field_generator = MongoFormFieldGenerator()

        for field_num in range(list_size):
            field_name = '%s%s%s' % (
                field_name_base, self.field_name_separator, field_num)
            self.fields.append(field_generator.generate(field_name, field))

        self.widget = ListWidget(
            widgets=map(attrgetter('widget'), self.fields))


class EmbeddedDocumentField(forms.Field):

    def __init__(self, field, field_name, *args, **kwargs):
        from forms import MongoForm
        super(EmbeddedDocumentField, self).__init__(*args, **kwargs)
        meta = type('Meta', (), {'document': field.document_type_obj})
        self.form = type('%sForm' % field_name, (MongoForm,), {'Meta': meta})


class MongoFormFieldGenerator(object):
    """This class generates Django form-fields for mongoengine-fields."""

    def generate(self, field_name, field):
        """Tries to lookup a matching formfield generator (lowercase
        field-classname) and raises a NotImplementedError of no generator
        can be found.
        """
        if hasattr(self, 'generate_%s' % field.__class__.__name__.lower()):
            return getattr(self, 'generate_%s' % \
                field.__class__.__name__.lower())(field_name, field)
        else:
            raise NotImplementedError('%s is not supported by MongoForm' % \
                field.__class__.__name__)

    def generate_stringfield(self, field_name, field):
        if field.regex:
            return forms.CharField(
                regex=field.regex,
                required=field.required,
                min_length=field.min_length,
                max_length=field.max_length,
                initial=field.default
            )
        elif field.choices:
            return forms.ChoiceField(
                required=field.required,
                initial=field.default,
                choices=zip(field.choices, field.choices)
            )
        elif field.max_length is None:
            return forms.CharField(
                required=field.required,
                initial=field.default,
                min_length=field.min_length,
                widget=forms.Textarea
            )
        else:
            return forms.CharField(
                required=field.required,
                min_length=field.min_length,
                max_length=field.max_length,
                initial=field.default
            )

    def generate_emailfield(self, field_name, field):
        return forms.EmailField(
            required=field.required,
            min_length=field.min_length,
            max_length=field.max_length,
            initial=field.default
        )

    def generate_urlfield(self, field_name, field):
        return forms.URLField(
            required=field.required,
            min_length=field.min_length,
            max_length=field.max_length,
            initial=field.default
        )

    def generate_intfield(self, field_name, field):
        return forms.IntegerField(
            required=field.required,
            min_value=field.min_value,
            max_value=field.max_value,
            initial=field.default
        )

    def generate_floatfield(self, field_name, field):
        return forms.FloatField(
            required=field.required,
            min_value=field.min_value,
            max_value=field.max_value,
            initial=field.default
        )

    def generate_decimalfield(self, field_name, field):
        return forms.DecimalField(
            required=field.required,
            min_value=field.min_value,
            max_value=field.max_value,
            initial=field.default
        )

    def generate_booleanfield(self, field_name, field):
        return forms.BooleanField(
            required=field.required,
            initial=field.default
        )

    def generate_datetimefield(self, field_name, field):
        return forms.DateTimeField(
            required=field.required,
            initial=field.default
        )

    def generate_referencefield(self, field_name, field):
        return ReferenceField(field.document_type.objects)

    def generate_listfield(self, field_name, field):
        return ListField(
            field=field.field,  # inner_field = this_field.inner_field
            field_name_base=field_name,
            required=field.required,
            initial=field.default)

    def generate_embeddeddocumentfield(self, field_name, field):
        return EmbeddedDocumentField(
            field=field,
            field_name=field_name,
            required=field.required,
            initial=field.default)
