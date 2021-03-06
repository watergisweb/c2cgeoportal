# -*- coding: utf-8 -*-

# Copyright (c) 2013, Camptocamp SA
# All rights reserved.

# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:

# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.

# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.


import math
from decimal import Decimal

from pyramid.view import view_config
from pyramid.response import Response
from pyramid.httpexceptions import HTTPNotFound

import geojson
from c2cgeoportal.views.raster import Raster


class Profile(Raster):

    def __init__(self, request):
        self.request = request
        request.response.cache_control = "no-cache"
        Raster.__init__(self, request)

    @view_config(route_name='profile.json', renderer='decimaljson')
    def json(self):
        """answers to /profile.json"""
        layer, points = self._compute_points()
        return {'profile': points}

    @view_config(route_name='profile.csv')
    def csv(self):
        """answers to /profile.csv"""
        layers, points = self._compute_points()

        result = "distance," + ','.join(layers) + ",x,y"
        template = ','.join('%s' for l in layers)
        for point in points:
            r = template % tuple((str(point['values'][l]) for l in layers))
            result += '\n%s,%s,%d,%d' % (str(point['dist']), r, point['x'], point['y'])

        response = Response(result, cache_control="no-cache", headers={
            'Content-Type': 'text/csv; charset=utf-8',
            'Content-Disposition': 'attachment; filename="profil.csv"'
        })
        return response

    def _compute_points(self):
        """Compute the alt=fct(dist) array"""
        geom = geojson.loads(self.request.params['geom'], object_hook=geojson.GeoJSON.to_instance)

        if 'layers' in self.request.params:
            rasters = {}
            layers = self.request.params['layers'].split(',')
            for layer in layers:
                if layer in self.rasters:
                    rasters[layer] = self.rasters[layer]
                else:
                    raise HTTPNotFound("Layer %s not found" % layer)
        else:
            rasters = self.rasters

        points = []

        dist = 0
        prev_coord = None
        coords = self._create_points(geom.coordinates, int(self.request.params['nbPoints']))
        for coord in coords:
            if prev_coord is not None:
                dist += self._dist(prev_coord, coord)

            values = {}
            has_one = False
            for ref in rasters.keys():
                value = self._get_raster_value(
                    self.rasters[ref],
                    ref, coord[0], coord[1])
                if value is not None:
                    values[ref] = value
                    has_one = True

            if has_one:
                # 10cm accuracy is enough for distances
                rounded_dist = Decimal(str(dist)).quantize(Decimal('0.1'))
                points.append({
                    'dist': rounded_dist,
                    'values': values,
                    'x': coord[0],
                    'y': coord[1]
                })
            prev_coord = coord

        return rasters.keys(), points

    def _dist(self, coord1, coord2):
        """Compute the distance between 2 points"""
        return math.sqrt(math.pow(coord1[0] - coord2[0], 2.0) +
                         math.pow(coord1[1] - coord2[1], 2.0))

    def _create_points(self, coords, nbPoints):
        """Add some points in order to reach roughly the asked number of points"""
        totalLength = 0
        prev_coord = None
        for coord in coords:
            if prev_coord is not None:
                totalLength += self._dist(prev_coord, coord)
            prev_coord = coord

        if totalLength == 0.0:
            return coords

        result = []
        prev_coord = None
        for coord in coords:
            if prev_coord is not None:
                cur_length = self._dist(prev_coord, coord)
                cur_nb_points = int(nbPoints * cur_length / totalLength + 0.5)
                if cur_nb_points < 1:
                    cur_nb_points = 1
                dx = (coord[0] - prev_coord[0]) / float(cur_nb_points)
                dy = (coord[1] - prev_coord[1]) / float(cur_nb_points)
                for i in range(1, cur_nb_points):
                    result.append([prev_coord[0] + dx * i, prev_coord[1] + dy * i])
            else:
                result.append([coord[0], coord[1]])
            prev_coord = coord
        return result
