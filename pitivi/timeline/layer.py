# -- coding: utf-8 --
# Pitivi video editor
#
#       pitivi/timeline/layer.py
#
# Copyright (c) 2012, Paul Lange <palango@gmx.de>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this program; if not, write to the
# Free Software Foundation, Inc., 51 Franklin St, Fifth Floor,
# Boston, MA 02110-1301, USA.

from gi.repository import Gdk
from gi.repository import Gtk
from gi.repository import GES
from gi.repository import Gio
from gi.repository import GObject

from gettext import gettext as _

from pitivi.timeline import elements
from pitivi.utils.loggable import Loggable
from pitivi.utils import ui
from pitivi.utils import timeline as timelineUtils


class BaseLayerControl(Gtk.Box, Loggable):

    """
    Base Layer control classes
    """

    __gtype_name__ = 'LayerControl'

    def __init__(self, control_container, layer, app, type_name):
        Gtk.Box.__init__(self, spacing=0)
        Loggable.__init__(self)

        self._app = app
        self._control_container = control_container
        self.layer = layer
        self._selected = False
        self.__type_name = type_name
        self.__meta_name = type_name + "::name"

        context = self.get_style_context()

        # get the default color for the current theme
        self.UNSELECTED_COLOR = context.get_background_color(
            Gtk.StateFlags.NORMAL)
        # use base instead of bg colors so that we get the lighter color
        # that is used for list items in TreeView.
        self.SELECTED_COLOR = context.get_background_color(
            Gtk.StateFlags.SELECTED)

        self.set_orientation(Gtk.Orientation.VERTICAL)

        table = Gtk.Table(n_rows=2, n_columns=2)
        table.set_border_width(ui.PADDING)
        table.set_row_spacings(3)
        table.set_col_spacings(3)

        self.pack_start(table, True, True, 0)

        self.name_entry = Gtk.Entry()
        self.name_entry.set_tooltip_text(
            _("Set a personalized name for this layer"))
        self.name_entry.set_property("secondary-icon-name", self._getIconName())
        self.name_entry.connect("key-press-event", self._keyPressCb)
        if layer.bLayer.get_meta(self.__meta_name) is None:
            self.layer.bLayer.set_meta(self.__meta_name, '%s %d'
                                       % (self.__type_name, layer.bLayer.get_priority()))
        self.name_entry.set_text(self.layer.bLayer.get_meta(self.__meta_name))

        table.attach(self.name_entry, 0, 2, 0, 2)

        self.show_all()

    def _getIconName(self):
        return None

    def getSelected(self):
        return self._selected

    def setSelected(self, selected):
        if selected != self._selected:
            self._selected = selected
            self._selectionChangedCb()

    selected = property(getSelected, setSelected, None, "Selection state")

    def _selectionChangedCb(self):
        """
        Called when the selection state changes
        """
        if self.selected:
            self.name_entry.override_background_color(
                Gtk.StateType.NORMAL, self.SELECTED_COLOR)
        else:
            self.name_entry.override_background_color(
                Gtk.StateType.NORMAL, self.UNSELECTED_COLOR)

        # continue GTK signal propagation
        return True

    def _keyPressCb(self, unused_widget, event):
        self.layer.bLayer.set_meta(self.__meta_name, self.name_entry.get_text())
        self._app.project_manager.current_project.setModificationState(True)

    def getHeight(self):
        return self.get_allocation().height

    def getSeparatorHeight(self):
        return self.sep.get_allocation().height

    def getControlHeight(self):
        return self.getHeight() - self.getSeparatorHeight()

    def setSoloState(self, state):
        self.solo_button.set_active(state)

    def setSeparatorVisibility(self, visible):
        if visible:
            self.sep.show()
        else:
            self.sep.hide()


class VideoLayerControl(BaseLayerControl):
    """
    Layer control class for video layers
    """

    __gtype_name__ = 'VideoLayerControl'

    def __init__(self, control_container, layer, app):
        BaseLayerControl.__init__(self, control_container, layer, app, "video")

    def _getIconName(self):
        return "video-x-generic"


class AudioLayerControl(BaseLayerControl):
    """
    Layer control class for audio layers
    """

    __gtype_name__ = 'AudioLayerControl'

    def __init__(self, control_container, layer, app):
        BaseLayerControl.__init__(self, control_container, layer, app, "audio")

    def _getIconName(self):
        return "audio-x-generic"


class TwoStateButton(Gtk.Button):
    """
    Button with two states and according labels/images
    """

    __gsignals__ = {
        "changed-state": (GObject.SignalFlags.RUN_LAST, None, (GObject.TYPE_PYOBJECT,),)
    }

    def __init__(self, state1="", state2=""):
        Gtk.Button.__init__(self)
        self.set_relief(Gtk.ReliefStyle.NONE)
        self.connect("clicked", self._clickedCb)

        self.set_states(state1, state2)
        self._state = True

        self.set_label(self.states[self._state])

    def set_states(self, state1, state2):
        self.states = {True: state1, False: state2}

    def _clickedCb(self, unused_widget):
        self._state = not self._state

        self.set_label(self.states[self._state])
        self.emit("changed-state", self._state)


class SpacedSeparator(Gtk.EventBox):
    """
    A Separator with vertical spacing

    Inherits from EventBox since we want to change background color
    """

    def __init__(self):
        Gtk.EventBox.__init__(self)

        self.box = Gtk.Box()
        self.box.set_orientation(Gtk.Orientation.VERTICAL)
        self.add(self.box)

        self.get_style_context().add_class("SpacedSeparator")
        self.box.get_style_context().add_class("SpacedSeparator")
        self.props.height_request = ui.PADDING


class LayerControls(Gtk.Bin, Loggable):

    __gtype_name__ = 'PitiviLayerControls'

    def __init__(self, bLayer, app):
        super(LayerControls, self).__init__()
        Loggable.__init__(self)

        ebox = Gtk.EventBox()
        self.add(ebox)
        self._vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self._hbox = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        ebox.add(self._hbox)
        self.bLayer = bLayer
        self.app = app

        sep = SpacedSeparator()
        self._vbox.pack_start(sep, False, False, 0)

        menubutton = Gtk.MenuButton.new()
        model, action_group = self.__createMenuModel()
        popover = Gtk.Popover.new_from_model(menubutton, model)
        popover.insert_action_group("layer", action_group)

        menubutton.set_popover(popover)
        menubutton.props.direction = Gtk.ArrowType.RIGHT
        self._hbox.add(menubutton)
        self._hbox.add(self._vbox)
        popover.props.position = Gtk.PositionType.LEFT

        self.video_control = VideoLayerControl(None, self, self.app)
        self.video_control.set_visible(True)
        self.video_control.props.height_request = ui.LAYER_HEIGHT / 2
        self._vbox.add(self.video_control)

        self.audio_control = AudioLayerControl(None, self, self.app)
        self.audio_control.set_visible(True)
        self.audio_control.props.height_request = ui.LAYER_HEIGHT / 2
        self._vbox.add(self.audio_control)

        sep = SpacedSeparator()
        self._vbox.pack_start(sep, False, False, 0)

        self._vbox.props.vexpand = False
        self.props.width_request = ui.CONTROL_WIDTH
        self.props.height_request = ui.LAYER_HEIGHT

        self.bLayer.connect("notify::priority", self.__layerPriorityChangedCb)
        self.__layerPriorityChangedCb(self.bLayer, None)

        ebox.connect("notify::window", self._windowSetCb)

    def _windowSetCb(self, window, pspec):
        self.props.window.set_cursor(Gdk.Cursor.new(Gdk.CursorType.HAND1))

    def __del__(self):
        self.bLayer.disconnect_by_func(self.__layerPriorityChangedCb)
        super(LayerControls, self).__del__()

    def __layerPriorityChangedCb(self, bLayer, pspec):
        if bLayer.get_priority() == 0:
            self.__move_layer_up_action.props.enabled = False
            self.__move_layer_top_action.props.enabled = False
        else:
            self.__move_layer_up_action.props.enabled = True
            self.__move_layer_top_action.props.enabled = True

    def __createMenuModel(self):
        action_group = Gio.SimpleActionGroup()
        menu_model = Gio.Menu()

        self.__move_layer_top_action = action = Gio.SimpleAction.new("move_layer_to_top", None)
        action.connect("activate", self._moveLayerCb, -2)
        action_group.insert(action)
        menu_model.append(_("Move layer to top"), "layer.%s" % action.get_name().replace(" ", "."))

        self.__move_layer_up_action = action = Gio.SimpleAction.new("move_layer_up", None)
        action.connect("activate", self._moveLayerCb, -1)
        action_group.insert(action)
        menu_model.append(_("Move layer up"), "layer.%s" % action.get_name().replace(" ", "."))

        action = Gio.SimpleAction.new("move_layer_down", None)
        action.connect("activate", self._moveLayerCb, 1)
        action_group.insert(action)
        menu_model.append(_("Move layer down"), "layer.%s" % action.get_name().replace(" ", "."))

        action = Gio.SimpleAction.new("move_layer_to_bottom", None)
        action.connect("activate", self._moveLayerCb, 2)
        action_group.insert(action)
        menu_model.append(_("Move layer to bottom"), "layer.%s" % action.get_name().replace(" ", "."))

        action = Gio.SimpleAction.new("delete_layer", None)
        action.connect("activate", self._deleteLayerCb)
        action_group.insert(action)
        menu_model.append(_("Delete layer"), "layer.%s" % action.get_name())

        return menu_model, action_group

    def _deleteLayerCb(self, unused_action, unused_parametter):
        self.app.action_log.begin("delete layer")
        bLayer = self.bLayer
        bTimeline = bLayer.get_timeline()
        bTimeline.remove_layer(bLayer)
        bTimeline.get_asset().pipeline.commit_timeline()
        self.app.action_log.commit()

    def _moveLayerCb(self, unused_simple_action, unused_parametter, step):
        index = self.bLayer.get_priority()
        if abs(step) == 1:
            index += step
        elif step == -2:
            index = 0
        else:
            index = len(self.bLayer.get_timeline().get_layers()) - 1
            # if audio, set last position
        self.bLayer.get_timeline().ui.moveLayer(self.bLayer, index)
        self.app.project_manager.current_project.pipeline.commit_timeline()


class LayerLayout(Gtk.Layout, Loggable):
    """
    A GtkLayout that exclusivly container Clips.
    This allows us to properly handle the z order of
    """
    __gtype_name__ = "PitiviLayerLayout"

    def __init__(self, timeline):
        super(LayerLayout, self).__init__()
        Loggable.__init__(self)

        self._children = []
        self._changed = False
        self.timeline = timeline

        self.props.hexpand = True
        self.get_style_context().add_class("LayerLayout")

    def do_add(self, widget):
        self._children.append(widget)
        self._children.sort(key=lambda clip: clip.z_order)
        Gtk.Layout.do_add(self, widget)
        self._changed = True

        for child in self._children:
            if isinstance(child, elements.TransitionClip):
                window = child.get_window()
                if window is not None:
                    window.raise_()

    def do_remove(self, widget):
        self._children.remove(widget)
        self._changed = True
        Gtk.Layout.do_remove(self, widget)

    def put(self, child, x, y):
        self._children.append(child)
        self._children.sort(key=lambda clip: clip.z_order)
        Gtk.Layout.put(self, child, x, y)
        self._changed = True

    def do_draw(self, cr):
        if self._changed:
            self._children.sort(key=lambda clip: clip.z_order)
            for child in self._children:

                if isinstance(child, elements.TransitionClip):
                    window = child.get_window()
                    window.raise_()
            self._changed = False

        self.props.width = max(self.timeline.layout.get_allocation().width,
                               timelineUtils.Zoomable.nsToPixel(self.timeline.bTimeline.props.duration))
        self.props.width_request = max(self.timeline.layout.get_allocation().width,
                                       timelineUtils.Zoomable.nsToPixel(self.timeline.bTimeline.props.duration))

        for child in self._children:
            self.propagate_draw(child, cr)


class Layer(Gtk.EventBox, timelineUtils.Zoomable, Loggable):

    __gtype_name__ = "PitiviLayer"

    __gsignals__ = {
        "remove-me": (GObject.SignalFlags.RUN_LAST, None, (),)
    }

    def __init__(self, bLayer, timeline):
        super(Layer, self).__init__()
        Loggable.__init__(self)

        self.bLayer = bLayer
        self.bLayer.ui = self
        self.timeline = timeline
        self.app = timeline.app

        self.bLayer.connect("clip-added", self._clipAddedCb)
        self.bLayer.connect("clip-removed", self._clipRemovedCb)

        # FIXME Make the layer height user setable with 'Paned'
        self.props.height_request = ui.LAYER_HEIGHT
        self.props.valign = Gtk.Align.START

        self._layout = LayerLayout(self.timeline)
        self.add(self._layout)

        self.media_types = GES.TrackType(0)
        for clip in bLayer.get_clips():
            self._addClip(clip)

        self.before_sep = None
        self.after_sep = None

    def release(self):
        for clip in self.bLayer.get_clips():
            self._removeClip(clip)
        self.bLayer.disconnect_by_func(self._clipAddedCb)
        self.bLayer.disconnect_by_func(self._clipRemovedCb)

    def checkMediaTypes(self, bClip=None):
        if self.timeline.editing_context:
            self.info("Not updating media types as"
                      " we are editing the timeline")
            return
        self.media_types = GES.TrackType(0)
        bClips = self.bLayer.get_clips()

        """
        FIXME: That produces segfault in GES/GSequence
        if not bClips:
            self.emit("remove-me")
            return
        """

        for bClip in bClips:
            for child in bClip.get_children(False):
                self.media_types |= child.get_track().props.track_type
                if self.media_types == (GES.TrackType.AUDIO | GES.TrackType.VIDEO):
                    break

        if not (self.media_types & GES.TrackType.AUDIO) and not (self.media_types & GES.TrackType.VIDEO):
            self.media_types = GES.TrackType.AUDIO | GES.TrackType.VIDEO

        height = 0
        if self.media_types & GES.TrackType.AUDIO:
            height += ui.LAYER_HEIGHT / 2
            self.bLayer.control_ui.audio_control.show()
        else:
            self.bLayer.control_ui.audio_control.hide()

        if self.media_types & GES.TrackType.VIDEO:
            self.bLayer.control_ui.video_control.show()
            height += ui.LAYER_HEIGHT / 2
        else:
            self.bLayer.control_ui.video_control.hide()

        self.props.height_request = height
        self.bLayer.control_ui.props.height_request = height

    def move(self, child, x, y):
        self._layout.move(child, x, y)

    def _childAddedCb(self, bClip, child):
        self.checkMediaTypes()

    def _childRemovedCb(self, bClip, child):
        self.checkMediaTypes()

    def _clipAddedCb(self, layer, bClip):
        self._addClip(bClip)

    def _addClip(self, bClip):
        ui_type = elements.GES_TYPE_UI_TYPE.get(bClip.__gtype__, None)
        if ui_type is None:
            self.error("Implement UI for type %s?" % bClip.__gtype__)
            return

        if not hasattr(bClip, "ui") or bClip.ui is None:
            clip = ui_type(self, bClip)
        else:
            clip = bClip.ui

        self._layout.put(clip, self.nsToPixel(bClip.props.start), 0)
        self.show_all()
        bClip.connect_after("child-added", self._childAddedCb)
        bClip.connect_after("child-removed", self._childRemovedCb)
        self.checkMediaTypes()

    def _clipRemovedCb(self, bLayer, bClip):
        self._removeClip(bClip)

    def _removeClip(self, bClip):
        ui_type = elements.GES_TYPE_UI_TYPE.get(bClip.__gtype__, None)
        if ui_type is None:
            self.error("Implement UI for type %s?" % bClip.__gtype__)
            return

        self._layout.remove(bClip.ui)
        bClip.ui.layer = None
        if self.timeline.draggingElement is None:
            bClip.ui = None

        bClip.disconnect_by_func(self._childAddedCb)
        bClip.disconnect_by_func(self._childRemovedCb)
        self.checkMediaTypes(bClip)

    def updatePosition(self):
        for bClip in self.bLayer.get_clips():
            bClip.ui.updatePosition()

    def do_draw(self, cr):
        Gtk.Box.do_draw(self, cr)
