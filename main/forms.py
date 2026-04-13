
from django import forms
from .models import Situation, Strategy, Step

class SituationForm(forms.ModelForm):
    class Meta:
        model = Situation
        fields = ['type', 'description']

class StrategyForm(forms.ModelForm):
    class Meta:
        model = Strategy
        fields = ['field1', 'field2', 'field3']

class StepForm(forms.ModelForm):
    class Meta:
        model = Step
        fields = ['title', 'description', 'responsible', 'duration']
