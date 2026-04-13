
from django.db import models
from django.contrib.auth.models import User

class Situation(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    type = models.CharField(max_length=255)
    description = models.TextField()

class Strategy(models.Model):
    situation = models.ForeignKey(Situation, on_delete=models.CASCADE)
    field1 = models.CharField(max_length=255, blank=True)
    field2 = models.CharField(max_length=255, blank=True)
    field3 = models.CharField(max_length=255, blank=True)

class Step(models.Model):
    strategy = models.ForeignKey(Strategy, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)
    description = models.TextField()
    responsible = models.CharField(max_length=255)
    duration = models.CharField(max_length=100)

    def __str__(self):
        return self.title
