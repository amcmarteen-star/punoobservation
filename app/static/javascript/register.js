/* Register page: Province -> Municipality / City -> Barangay -> Organization.
   Each list stays locked until the one before it has a value. The data
   comes from the #register-data JSON block that Register.html renders. */
(function () {
    'use strict';

    var dataEl = document.getElementById('register-data');
    if (!dataEl) { return; }
    var data = JSON.parse(dataEl.textContent);

    var province = document.getElementById('reg_province');
    var municipality = document.getElementById('reg_municipality');
    var barangay = document.getElementById('location_id');
    var organization = document.getElementById('organization_id');

    function unique(values) {
        return values.filter(function (v, i) { return values.indexOf(v) === i; });
    }

    // Empties a list, puts back its prompt, then adds the given options.
    function fill(select, prompt, options) {
        select.innerHTML = '';
        var first = document.createElement('option');
        first.value = '';
        first.textContent = prompt;
        select.appendChild(first);
        options.forEach(function (o) {
            var opt = document.createElement('option');
            opt.value = o.value;
            opt.textContent = o.label;
            select.appendChild(opt);
        });
        select.disabled = false;
    }

    function lock(select, prompt) {
        fill(select, prompt, []);
        select.disabled = true;
    }

    function asOptions(names) {
        return names.map(function (n) { return { value: n, label: n }; });
    }

    function onProvince() {
        lock(barangay, 'Choose a municipality first');
        lock(organization, 'Choose a barangay first');
        if (!province.value) {
            lock(municipality, 'Choose a province first');
            return;
        }
        var names = unique(data.locations
            .filter(function (l) { return l.province === province.value; })
            .map(function (l) { return l.municipality; }));
        fill(municipality, 'Choose a municipality or city', asOptions(names));
    }

    function onMunicipality() {
        lock(organization, 'Choose a barangay first');
        if (!municipality.value) {
            lock(barangay, 'Choose a municipality first');
            return;
        }
        var options = data.locations
            .filter(function (l) {
                return l.province === province.value &&
                       l.municipality === municipality.value;
            })
            .map(function (l) { return { value: l.id, label: l.barangay }; });
        fill(barangay, 'Choose a barangay', options);
    }

    function onBarangay() {
        if (!barangay.value) {
            lock(organization, 'Choose a barangay first');
            return;
        }
        var id = Number(barangay.value);
        var options = data.organizations
            .filter(function (o) { return o.locations.indexOf(id) !== -1; })
            .map(function (o) { return { value: o.id, label: o.label }; });
        fill(organization, 'None / Individual User', options);
        organization.options[0].selected = true;
    }

    province.addEventListener('change', onProvince);
    municipality.addEventListener('change', onMunicipality);
    barangay.addEventListener('change', onBarangay);

    fill(province, 'Choose a province',
        asOptions(unique(data.locations.map(function (l) { return l.province; }))));

    // Only one province: choose it so the user starts at municipality.
    if (province.options.length === 2) {
        province.selectedIndex = 1;
        onProvince();
    }

    // After a failed sign-up, put the user's earlier choices back.
    var chosen = data.locations.filter(function (l) {
        return String(l.id) === String(data.location_id);
    })[0];
    if (chosen) {
        province.value = chosen.province;
        onProvince();
        municipality.value = chosen.municipality;
        onMunicipality();
        barangay.value = String(chosen.id);
        onBarangay();
        organization.value = String(data.organization_id || '');
    }
}());
