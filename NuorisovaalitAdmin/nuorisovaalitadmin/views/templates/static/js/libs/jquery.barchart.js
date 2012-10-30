/*
 * <OpenID voting platform> Copyright (c) 2012  Suomen Verkkodemokratiaseura ry  <toimisto@verkkodemokratia.fi> This program is free software: you can redistribute it and/or modify it under the terms of the GNU Affero General Public License as published by the Free Software Foundation, either version 3 of the License, or (at your option) any later version. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the file LICENSE.TXT in the root directory of this program and GNU Affero General Public License for more details. You should have received a copy of the GNU Affero General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */
/*jslint white: true, browser: true, devel: true, onevar: true, undef: true, nomen: true, eqeqeq: true, plusplus: true, bitwise: true, regexp: true, newcap: true, immed: true */
/*global window:false, jQuery:false*/
(function ($) {
    var getHtml;

    // Construct the markup for the chart.
    //
    // @param leftPercent (number) width of the left bar (0...100)
    // @param rightPercent (number) width of the right bar (0...100)
    // @param config (object) settings for the plugin
    getHtml = function (leftPercent, rightPercent, config) {
        var $wrapper, $bar;

        $wrapper = $('<div></div>').addClass('barchart');
        if (!leftPercent && !rightPercent) {
            $wrapper.addClass('barchart-empty');
        }

        $('<p></p>')
            .addClass('barchart-label-left')
            .html(config.leftLabel + ' ' + leftPercent + ' %')
            .appendTo($wrapper);
        $('<p></p>')
            .addClass('barchart-label-right')
            .html(config.rightLabel + ' ' + rightPercent + ' %')
            .appendTo($wrapper);

        $bar = $('<div></div>').addClass('barchart-bar');
        $('<div></div>')
            .addClass('barchart-bar-left')
            .css('width', leftPercent + '%')
            .appendTo($bar);
        $bar.appendTo($wrapper);

        return $wrapper;
    };

    // jQuery entry point.
    $.fn.barchart = function (leftPercent, rightPercent, options) {
        return $(this).each(function () {
            var settings, $container, $markup;
            settings = $.extend({}, $.fn.barchart.defaults, options || {});
            $container = $(this);
            $markup = getHtml(leftPercent, rightPercent, settings);
            $container.empty().html($markup);
        });
    };

    // Default configuration.
    $.fn.barchart.defaults = {
        leftLabel: 'Yes',
        rightLabel: 'No'
    };

}(jQuery));
