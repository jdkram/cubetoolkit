from django.db import migrations


def populate_suppliers_from_records(apps, schema_editor):
    SupplierRecord = apps.get_model("labs", "SupplierRecord")
    Supplier = apps.get_model("labs", "Supplier")
    Volunteer = apps.get_model("members", "Volunteer")

    seen = {}
    for record in SupplierRecord.objects.filter(supplier_name__gt="").select_related():
        name = record.supplier_name.strip()
        if not name:
            continue
        if name not in seen:
            supplier, _ = Supplier.objects.get_or_create(name=name)
            # lift account_holder to Supplier on first encounter
            if record.account_holder_id and supplier.account_holder_id is None:
                supplier.account_holder_id = record.account_holder_id
                supplier.save()
            seen[name] = supplier
        record.supplier = seen[name]
        record.save()


def reverse_migration(apps, schema_editor):
    SupplierRecord = apps.get_model("labs", "SupplierRecord")
    SupplierRecord.objects.update(supplier=None)


class Migration(migrations.Migration):

    dependencies = [
        ("labs", "0026_supplier_and_pledge_status"),
    ]

    operations = [
        migrations.RunPython(populate_suppliers_from_records, reverse_migration),
    ]
