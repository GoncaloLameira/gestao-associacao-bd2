from django.db import models


class Mandato(models.Model):
    id_mandato = models.AutoField(primary_key=True)
    data_inicio = models.DateField()
    data_fim = models.DateField()
    id_associacao = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'mandato'

    def __str__(self):
        return f"Mandato {self.id_mandato}"


class ExercicioCargo(models.Model):
    id_exercicio_cargo = models.AutoField(primary_key=True)
    data_inicio = models.DateField()
    data_fim = models.DateField(null=True, blank=True)
    id_associado = models.IntegerField()
    id_cargo = models.IntegerField()
    id_mandato = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'exercicio_cargo'

    def __str__(self):
        return f"Exercício de Cargo {self.id_exercicio_cargo}"